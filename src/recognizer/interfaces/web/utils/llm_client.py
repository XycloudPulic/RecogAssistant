# SPDX-License-Identifier: MIT

"""大模型客户端模块

支持OpenAI和Ollama两种LLM提供商
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import streamlit as st
from openai import OpenAI


@dataclass
class LLMConfig:
    """LLM配置"""

    provider: str = "openai"  # openai 或 ollama
    api_key: str = ""
    endpoint: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"


class LLMClient:
    """大模型客户端（支持OpenAI和Ollama）"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None

    @property
    def client(self) -> OpenAI:
        """获取OpenAI客户端"""
        if self._client is None:
            if self.config.provider == "openai":
                self._client = OpenAI(
                    api_key=self.config.api_key, base_url=self.config.endpoint
                )
        return self._client

    def parse_with_prompt(
        self, ocr_text: str, prompt_template: str, json_schema: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """使用LLM解析发票

        Args:
            ocr_text: OCR识别的文本
            prompt_template: 提示词模板
            json_schema: JSON输出格式定义

        Returns:
            解析后的发票数据
        """
        # 构建提示词
        json_schema_str = json.dumps(json_schema, ensure_ascii=False, indent=2)
        prompt = prompt_template.replace("{{ocr_text}}", ocr_text)
        prompt = prompt.replace("{{json_schema}}", json_schema_str)

        try:
            if self.config.provider == "openai":
                return self._call_openai(prompt)
            elif self.config.provider == "ollama":
                return self._call_ollama(prompt)
            else:
                st.error(f"不支持的LLM提供商: {self.config.provider}")
                return None
        except Exception as e:
            st.error(f"LLM调用失败: {str(e)}")
            return None

    def _call_openai(self, prompt: str) -> Optional[Dict[str, Any]]:
        """调用OpenAI API"""
        if not self.config.api_key:
            st.warning("请先配置OpenAI API Key")
            return None

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": "你是一个专业的发票解析助手。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1000,
        )

        content = response.choices[0].message.content.strip()
        return self._parse_json_response(content)

    def _call_ollama(self, prompt: str) -> Optional[Dict[str, Any]]:
        """调用Ollama本地API"""
        import requests

        url = f"{self.config.ollama_host}/api/generate"
        payload = {
            "model": self.config.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1000},
        }

        response = requests.post(url, json=payload, timeout=120)

        if response.status_code == 200:
            content = response.json().get("response", "").strip()
            return self._parse_json_response(content)
        else:
            st.error(f"Ollama调用失败: {response.status_code}")
            return None

    def _parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        """解析LLM返回的JSON响应"""
        # 尝试提取JSON块
        content = content.strip()

        # 如果包含代码块，提取内部内容
        if content.startswith("```"):
            lines = content.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```"):
                    in_json = not in_json
                    continue
                if in_json:
                    json_lines.append(line)
            content = "\n".join(json_lines)

        # 尝试解析JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试查找JSON对象
            import re

            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            st.warning("无法解析LLM返回的JSON")
            return None

    @classmethod
    def from_openai(
        cls,
        api_key: str,
        endpoint: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
    ):
        """从OpenAI配置创建客户端"""
        config = LLMConfig(
            provider="openai", api_key=api_key, endpoint=endpoint, model=model
        )
        return cls(config)

    @classmethod
    def from_ollama(
        cls, host: str = "http://localhost:11434", model: str = "qwen2.5:7b"
    ):
        """从Ollama配置创建客户端"""
        config = LLMConfig(provider="ollama", ollama_host=host, ollama_model=model)
        return cls(config)


@st.cache_resource
def get_llm_client(provider: str, **kwargs) -> LLMClient:
    """获取LLM客户端实例"""
    config = LLMConfig(provider=provider, **kwargs)
    return LLMClient(config)
