# Import the updated, rule-first dynamic 'ast' classes
from .rule_classes import (
    APIAuthVisitor,
    GeneralAuthenticationVisitor,
    FunctionConstraintVisitor,
    ClassLengthAndConstraintVisitor,
    FunctionLengthVisitor,
    DocstringConstraintVisitor,
    ErrorHandlingConstraintVisitor,
    NPlusOneQueryConstraintVisitor,
    PiiLeakageConstraintVisitor
)

# Map your system configuration strings to the corrected 'ast' engines
AST_TOOL_REGISTRY = {
    "check_api_auth": APIAuthVisitor,
    "check_general_auth": GeneralAuthenticationVisitor,
    "check_transaction_atomic": FunctionConstraintVisitor,  # Handled by function constraints now!
    "check_required_call": FunctionConstraintVisitor,
    "check_class_length": ClassLengthAndConstraintVisitor,
    "check_function_length": FunctionLengthVisitor,
    "check_docstrings": DocstringConstraintVisitor,         # Brand new engine option!
    "check_error_handling": ErrorHandlingConstraintVisitor,
    "check_n_plus_one": NPlusOneQueryConstraintVisitor,
    "check_pii": PiiLeakageConstraintVisitor
}
