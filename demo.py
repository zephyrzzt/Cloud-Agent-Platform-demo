from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.sandbox.docker_sandbox_service import (
    DockerSandboxService,
)
from app.sandbox.sandbox_models import SandboxSpec


async def clone_repository(
    repository_url: str,
    destination: Path,
) -> None:
    """在可信 Setup 阶段克隆公开仓库。

    沙箱正式执行 Agent 任务时默认关闭网络，所以仓库拉取应在创建
    沙箱之前完成。生产环境中还需要进一步校验仓库地址、协议和大小。
    """

    await asyncio.to_thread(
        subprocess.run,
        [
            "git",
            "clone",
            "--depth=1",
            repository_url,
            str(destination),
        ],
        check=True,
        timeout=120,
        capture_output=True,
        text=True,
    )


async def main() -> None:
    """演示完整的沙箱创建、执行和清理流程。"""

    # 为本次任务创建独立临时目录。
    workspace = Path(
        tempfile.mkdtemp(prefix="cloud-agent-demo-")
    )

    repository_path = workspace / "repository"
    artifacts_path = workspace / "artifacts"

    # 当前原型最多允许两个沙箱同时运行。
    service = DockerSandboxService(
        max_num_sandboxes=2,
    )

    # 用于 finally 中清理容器。
    sandbox_id: str | None = None

    try:
        # 第一步：可信 Setup 阶段拉取仓库。
        await clone_repository(
            repository_url=(
                "https://github.com/pallets/flask.git"
            ),
            destination=repository_path,
        )

        artifacts_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        # 仅为简化本地 Demo 的 UID 权限问题。
        # 生产环境应使用精确的 UID/GID 所有权，而不是开放 777 权限。
        artifacts_path.chmod(0o777)

        # 第二步：构造与运行时无关的沙箱规格。
        spec = SandboxSpec(
            id="todo-analysis-v1",
            image="cloud-agent-sandbox:latest",
            repository_path=repository_path,
            artifacts_path=artifacts_path,
            created_by_user_id="demo-user",

            # Agent 正式执行阶段关闭网络。
            network_disabled=True,

            # 设置基础资源限制。
            cpu_cores=1.0,
            memory_limit="1g",
            pids_limit=128,

            # 设置单命令超时及最大输出。
            command_timeout_seconds=30,
            max_output_bytes=20_000,
        )

        # 第三步：创建 Docker 沙箱。
        sandbox = await service.start_sandbox(spec)
        sandbox_id = sandbox.id

        # 第四步：等待沙箱真正进入 RUNNING 状态。
        sandbox = await service.wait_for_sandbox_running(
            sandbox_id,
            timeout=20,
        )

        print("Sandbox information:")
        print(
            json.dumps(
                sandbox.model_dump(mode="json"),
                indent=2,
                ensure_ascii=False,
            )
        )

        # 第五步：在只读仓库中搜索待办标记。
        result = await service.execute(
            sandbox_id=sandbox_id,
            command=(
                "rg -n --hidden "
                "--glob '!.git/**' "
                "--glob '!node_modules/**' "
                "--glob '!dist/**' "
                "--glob '!build/**' "
                r"'\b(TODO|FIXME|HACK)\b' . "
                "| head -200"
            ),
        )

        print("\nCommand result:")
        print(
            json.dumps(
                result.model_dump(),
                indent=2,
                ensure_ascii=False,
            )
        )

        # 第六步：验证仓库目录确实为只读。
        # 该命令应执行失败，不能在源码目录创建文件。
        readonly_test = await service.execute(
            sandbox_id=sandbox_id,
            command="touch should-not-be-created.txt",
        )

        print("\nRead-only repository test:")
        print(
            json.dumps(
                readonly_test.model_dump(),
                indent=2,
                ensure_ascii=False,
            )
        )

        # 第七步：切换到可写产物目录，生成报告。
        artifact_result = await service.execute(
            sandbox_id=sandbox_id,
            workdir="/workspace/artifacts",
            command=(
                "printf '# TODO Report\\n\\n"
                "Generated inside the sandbox.\\n' "
                "> todo-report.md"
            ),
        )

        print("\nArtifact creation:")
        print(
            json.dumps(
                artifact_result.model_dump(),
                indent=2,
                ensure_ascii=False,
            )
        )

        print(
            "\nArtifact path:",
            artifacts_path / "todo-report.md",
        )

    finally:
        # 无论任务成功、失败还是中途抛出异常，都要删除容器。
        if sandbox_id is not None:
            await service.delete_sandbox(sandbox_id)

        # 清理宿主机临时目录。
        shutil.rmtree(
            workspace,
            ignore_errors=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
