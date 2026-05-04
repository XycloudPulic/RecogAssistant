# SPDX-License-Identifier: MIT

"""字段解析器模块"""

from .base_field_parser import (
    PARSER_REGISTRY,
    BaseFieldParser,
    CompositeFieldParser,
    CoordinateFieldParser,
    KeyValueFieldParser,
    RegexFieldParser,
    TableFieldParser,
    get_parser,
)

__all__ = [
    "BaseFieldParser",
    "RegexFieldParser",
    "CoordinateFieldParser",
    "KeyValueFieldParser",
    "TableFieldParser",
    "CompositeFieldParser",
    "get_parser",
    "PARSER_REGISTRY",
]
