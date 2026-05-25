# agents/tools/registry.py
from .rule_classes import (
    AuthenticationVisitor,
    RequiredCallVisitor,
    FunctionLengthVisitor,
    ClassLengthVisitor,
    ErrorHandlingVisitor,
    NPlusOneQueryVisitor,
    PiiLeakageVisitor
)

AST_TOOL_REGISTRY = {
    "check_auth": AuthenticationVisitor,
    "check_required_call": RequiredCallVisitor,
    "check_function_length": FunctionLengthVisitor,
    "check_class_length": ClassLengthVisitor,
    "check_error_handling": ErrorHandlingVisitor,
    "check_n_plus_one": NPlusOneQueryVisitor,
    "check_pii": PiiLeakageVisitor,
}
