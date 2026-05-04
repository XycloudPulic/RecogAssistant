# SPDX-License-Identifier: MIT

"""发票预览组件"""

from pathlib import Path
from typing import Optional

import streamlit as st
from PIL import Image


def display_invoice_image(image_path: Optional[str], width: int = 400) -> None:
    """显示发票图片预览

    Args:
        image_path: 图片路径
        width: 显示宽度
    """
    if image_path and Path(image_path).exists():
        try:
            image = Image.open(image_path)
            st.image(image, caption=f"发票图片: {Path(image_path).name}", width=width)
        except Exception as e:
            st.error(f"无法显示图片: {str(e)}")
    else:
        st.info("请上传发票图片")
