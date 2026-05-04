# SPDX-License-Identifier: MIT

"""API客户端模块"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

from recognizer.common.config.settings import Settings
from recognizer.common.utils.file import guess_mime_type


class OCRAPIClient:
    """OCR API客户端"""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or str(
            Settings.get("api.base_url", "http://127.0.0.1:8000")
        )
        self.timeout = int(Settings.get("api.timeout", 120))  # 处理OCR耗时

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Accept": "application/json",
        }

    def recognize(
        self,
        image_path: str,
        workflow_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """调用通用识别 API（与具体票据类型解耦）。

        Args:
            image_path: 输入图片/PDF 路径。
            workflow_id: 指定调度流程 ID，缺省使用默认流程。

        Returns:
            API 响应字典；失败时返回 None。
        """
        try:
            with open(image_path, "rb") as f:
                fn = Path(image_path).name or "upload"
                mime = guess_mime_type(fn)
                files = {"file": (fn, f, mime)}
                params: Dict[str, str] = {}
                if workflow_id is not None:
                    params["workflow_id"] = str(int(workflow_id))
                response = requests.post(
                    f"{self.base_url}/api/v1/recognition/parse",
                    files=files,
                    params=params or None,
                    timeout=self.timeout,
                    headers=self._get_headers(),
                )

            if response.status_code == 200:
                return response.json()
            st.error(f"API错误: {response.status_code} - {response.text}")
            return None
        except requests.exceptions.ConnectionError:
            st.error(f"无法连接到识别服务: {self.base_url}")
            return None
        except Exception as exc:  # noqa: BLE001 - surface to UI
            st.error(f"请求失败: {exc}")
            return None

    def get_health(self) -> bool:
        """检查服务健康状态"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def get_nodes(self) -> List[Dict[str, Any]]:
        """获取已注册节点列表"""
        # 模拟数据，实际可以通过API获取
        return [
            {"name": "paddleocr_regex", "enabled": True, "order": 10},
            {"name": "paddleocr_region", "enabled": False, "order": 20},
            {"name": "ppstructure", "enabled": False, "order": 30},
            {"name": "llm", "enabled": False, "order": 40},
            {"name": "merge_result", "enabled": True, "order": 100},
        ]

    def get_templates(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """获取模板列表"""
        response = requests.get(
            f"{self.base_url}/templates",
            params={"active_only": "1" if active_only else "0"},
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def get_template(self, template_id: int) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/templates/{template_id}",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def create_template(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/templates",
            json=payload,
            timeout=30,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def update_template(
        self, template_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = requests.put(
            f"{self.base_url}/templates/{template_id}",
            json=payload,
            timeout=30,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def delete_template(self, template_id: int) -> None:
        response = requests.delete(
            f"{self.base_url}/templates/{template_id}",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()

    # --------------------
    # Rulesets
    # --------------------
    def list_rulesets(self, active_only: bool = False) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/rulesets",
            params={"active_only": "1" if active_only else "0"},
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def create_ruleset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/rulesets",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def update_ruleset(
        self, ruleset_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = requests.put(
            f"{self.base_url}/rulesets/{ruleset_id}",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def delete_ruleset(self, ruleset_id: int) -> None:
        response = requests.delete(
            f"{self.base_url}/rulesets/{ruleset_id}",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()

    def list_rule_items(self, ruleset_id: int) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/rulesets/{ruleset_id}/items",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def list_data_fields(
        self, ruleset_id: int, active_only: bool = False
    ) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/rulesets/{ruleset_id}/data-fields",
            params={"active_only": "1" if active_only else "0"},
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def create_data_field(
        self, ruleset_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/rulesets/{ruleset_id}/data-fields",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def update_data_field(
        self, ruleset_id: int, field_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = requests.put(
            f"{self.base_url}/rulesets/{ruleset_id}/data-fields/{field_id}",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def delete_data_field(self, ruleset_id: int, field_id: int) -> None:
        response = requests.delete(
            f"{self.base_url}/rulesets/{ruleset_id}/data-fields/{field_id}",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()

    def create_rule_item(
        self, ruleset_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/rulesets/{ruleset_id}/items",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def update_rule_item(
        self, ruleset_id: int, item_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = requests.put(
            f"{self.base_url}/rulesets/{ruleset_id}/items/{item_id}",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def delete_rule_item(self, ruleset_id: int, item_id: int) -> None:
        response = requests.delete(
            f"{self.base_url}/rulesets/{ruleset_id}/items/{item_id}",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()

    def regex_test(self, pattern: str, text: str) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/rulesets/regex-test",
            json={"pattern": pattern, "text": text},
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    # --------------------
    # LLM configs
    # --------------------
    def list_llm_configs(self, active_only: bool = False) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/llm-configs",
            params={"active_only": "1" if active_only else "0"},
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def create_llm_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/llm-configs",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def update_llm_config(self, llm_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.put(
            f"{self.base_url}/llm-configs/{llm_id}",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def delete_llm_config(self, llm_id: int) -> None:
        response = requests.delete(
            f"{self.base_url}/llm-configs/{llm_id}",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()

    # --------------------
    # Nodes
    # --------------------
    def list_nodes(self) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/nodes", timeout=10, headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def create_node(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/nodes",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def update_node(self, node_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.put(
            f"{self.base_url}/nodes/{node_id}",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def delete_node(self, node_id: int) -> None:
        response = requests.delete(
            f"{self.base_url}/nodes/{node_id}", timeout=10, headers=self._get_headers()
        )
        response.raise_for_status()

    # --------------------
    # Export configs & export
    # --------------------
    def list_export_configs(self, active_only: bool = True) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/export-configs",
            params={"active_only": "1" if active_only else "0"},
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def create_export_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/export-configs",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def update_export_config(
        self, export_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = requests.put(
            f"{self.base_url}/export-configs/{export_id}",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def delete_export_config(self, export_id: int) -> None:
        response = requests.delete(
            f"{self.base_url}/export-configs/{export_id}",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()

    def generate_export(
        self,
        export_config_id: int,
        rows: List[Dict[str, Any]],
        template_ctx: Optional[Dict[str, Any]] = None,
        filename_overwrite: Optional[str] = None,
    ) -> bytes:
        payload: Dict[str, Any] = {
            "export_config_id": int(export_config_id),
            "rows": rows,
        }
        if template_ctx is not None:
            payload["template_ctx"] = template_ctx
        if filename_overwrite:
            payload["filename_overwrite"] = filename_overwrite

        response = requests.post(
            f"{self.base_url}/exports/generate",
            json=payload,
            timeout=60,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.content

    # --------------------
    # Recognition history
    # --------------------
    def list_recognition_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/recognition/jobs",
            params={"limit": int(limit)},
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def list_recognition_runs(
        self, job_id: int, limit: int = 20
    ) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/recognition/jobs/{int(job_id)}/runs",
            params={"limit": int(limit)},
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def rerun_recognition_job(self, job_id: int) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/recognition/jobs/{int(job_id)}/rerun",
            timeout=120,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def export_from_runs(
        self,
        export_config_id: int,
        *,
        run_ids: Optional[List[int]] = None,
        latest_per_job: bool = True,
        job_ids: Optional[List[int]] = None,
        filename_overwrite: Optional[str] = None,
    ) -> bytes:
        payload: Dict[str, Any] = {"export_config_id": int(export_config_id)}
        if run_ids:
            payload["run_ids"] = [int(x) for x in run_ids]
        else:
            payload["latest_per_job"] = bool(latest_per_job)
            if job_ids:
                payload["job_ids"] = [int(x) for x in job_ids]
        if filename_overwrite:
            payload["filename_overwrite"] = filename_overwrite

        response = requests.post(
            f"{self.base_url}/exports/from-runs",
            json=payload,
            timeout=60,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.content

    # --------------------
    # Workflows
    # --------------------
    def list_workflows(self, active_only: bool = True) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/workflows",
            params={"active_only": "1" if active_only else "0"},
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def create_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/workflows",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def update_workflow(
        self, workflow_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = requests.put(
            f"{self.base_url}/workflows/{int(workflow_id)}",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def delete_workflow(self, workflow_id: int) -> None:
        response = requests.delete(
            f"{self.base_url}/workflows/{int(workflow_id)}",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()

    def get_workflow_nodes(self, workflow_id: int) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/workflows/{int(workflow_id)}/nodes",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def get_default_workflow_id(self) -> Optional[int]:
        response = requests.get(
            f"{self.base_url}/workflows/default",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        data = response.json() or {}
        v = data.get("default_workflow_id")
        return int(v) if v is not None else None

    def set_default_workflow(self, workflow_id: int) -> Dict[str, Any]:
        response = requests.put(
            f"{self.base_url}/workflows/{int(workflow_id)}/default",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    # --------------------
    # Validators
    # --------------------
    def list_validators(self, active_only: bool = True) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/validators",
            params={"active_only": "1" if active_only else "0"},
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def get_validator(self, validator_id: int) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/validators/{int(validator_id)}",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def create_validator(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/validators",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def update_validator(
        self, validator_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = requests.put(
            f"{self.base_url}/validators/{int(validator_id)}",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def delete_validator(self, validator_id: int) -> None:
        response = requests.delete(
            f"{self.base_url}/validators/{int(validator_id)}",
            timeout=10,
            headers=self._get_headers(),
        )
        response.raise_for_status()

    def test_validator(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/validators/test",
            json=payload,
            timeout=20,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()


# 全局客户端实例
@st.cache_resource
def get_api_client(base_url: str = "http://127.0.0.1:8000") -> OCRAPIClient:
    """获取API客户端实例"""
    return OCRAPIClient(base_url)
