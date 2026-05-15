# agents/tools/registry.py
from .rule_classes import (
    AuthDecoratorVisitor,
    RequiredCallVisitor,
    FunctionLengthVisitor,
    ClassLengthVisitor,
    ErrorHandlingVisitor,
    NPlusOneQueryVisitor,
    PiiLeakageVisitor
)

AST_TOOL_REGISTRY = {
    "check_auth": AuthDecoratorVisitor,
    "check_required_call": RequiredCallVisitor,
    "check_function_length": FunctionLengthVisitor,
    "check_class_length": ClassLengthVisitor,
    "check_error_handling": ErrorHandlingVisitor,
    "check_n_plus_one": NPlusOneQueryVisitor,
    "check_pii": PiiLeakageVisitor,
}
