import ast
import re

class BaseOdoziVisitor(ast.NodeVisitor):
    """Abstract base class ensuring a unified interface for all Odozi AST tools."""
    def __init__(self, params):
        self.params = params
        self.findings = []
        self._current_file = ""

    def analyze_file(self, file_path, source_code):
        self._current_file = file_path
        self.findings = []  # Reset findings per file
        try:
            tree = ast.parse(source_code)
            self.visit(tree)
        except SyntaxError:
            pass  # Avoid crashing on malformed or incomplete files
        return self.findings

    def _add_finding(self, rule_id, node, message):
        self.findings.append({
            "file": self._current_file,
            "rule_id": rule_id,
            "line": node.lineno,
            "message": message
        })


class AuthDecoratorVisitor(BaseOdoziVisitor):
    """Checks if functions matching a prefix are missing a mandatory decorator."""
    def visit_FunctionDef(self, node):
        prefix = self.params.get("function_prefix", "")
        decorator_name = self.params.get("decorator_name", "")
        
        if re.match(f"^{prefix}", node.name):
            has_decorator = False
            for dec in node.decorator_list:
                # Handle direct calls (@login_required) and factory calls (@permission_required('admin'))
                dec_name = dec.id if isinstance(dec, ast.Name) else getattr(getattr(dec, 'func', None), 'id', None)
                if dec_name == decorator_name:
                    has_decorator = True
                    break
            
            if not has_decorator:
                self._add_finding("missing_auth_decorator", node, 
                    f"Critical: Function '{node.name}' is missing the @{decorator_name} decorator.")
        self.generic_visit(node)


class RequiredCallVisitor(BaseOdoziVisitor):
    """Ensures specific functions wrap their execution with a required context or call."""
    def visit_FunctionDef(self, node):
        keyword = self.params.get("keyword", "")
        required_call = self.params.get("required_call", "")
        
        if keyword.lower() in node.name.lower():
            found = False
            for child in ast.walk(node):
                if isinstance(child, ast.Attribute) and child.attr == required_call:
                    found = True
                    break
                elif isinstance(child, ast.Name) and child.id == required_call:
                    found = True
                    break
            if not found:
                self._add_finding("missing_required_call", node, 
                    f"Function {node.name} matches keyword '{keyword}' but is missing required '{required_call}' call.")
        self.generic_visit(node)


class FunctionLengthVisitor(BaseOdoziVisitor):
    """Enforces maximum line limits on targeted functions."""
    def visit_FunctionDef(self, node):
        keyword = self.params.get("keyword", "")
        max_lines = int(self.params.get("max_lines", 50))
        
        if keyword.lower() in node.name.lower():
            actual_lines = node.end_lineno - node.lineno
            if actual_lines > max_lines:
                self._add_finding("function_too_large", node, 
                    f"Function {node.name} matches keyword '{keyword}' but exceeds the {max_lines}-line limit ({actual_lines} lines).")
        self.generic_visit(node)


class ClassLengthVisitor(BaseOdoziVisitor):
    """Enforces line boundaries on classes inheriting from specified models."""
    def visit_ClassDef(self, node):
        parent_class = self.params.get("parent_class", "")
        max_lines = int(self.params.get("max_lines", 100))
        
        inherits = False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == parent_class:
                inherits = True
            elif isinstance(base, ast.Attribute) and base.attr == parent_class:
                inherits = True
        
        if inherits:
            actual_lines = node.end_lineno - node.lineno
            if actual_lines > max_lines:
                self._add_finding("class_too_large", node, 
                    f"Class {node.name} inherits from {parent_class} but exceeds the {max_lines}-line limit ({actual_lines} lines).")
        self.generic_visit(node)


class ErrorHandlingVisitor(BaseOdoziVisitor):
    """Flags risky calls that are executed outside a try/except defensive safety net."""
    def visit_Call(self, node):
        risky_call = self.params.get("risky_call", "")
        
        is_target_call = False
        if isinstance(node.func, ast.Name) and node.func.id == risky_call:
            is_target_call = True
        elif isinstance(node.func, ast.Attribute) and node.func.attr == risky_call:
            is_target_call = True
            
        if is_target_call:
            # Check if this node is deeply encapsulated within a try block
            if not hasattr(node, '_in_try') or not node._in_try:
                self._add_finding("missing_try_except_request", node, 
                    f"Unsafe Execution: '{risky_call}' should be wrapped in a try/except block.")
        self.generic_visit(node)

    def visit_Try(self, node):
        """Custom walk modifier to inject contextual scope boundaries to child nodes."""
        for child in ast.walk(node):
            child._in_try = True
        self.generic_visit(node)


class NPlusOneQueryVisitor(BaseOdoziVisitor):
    """Performance analyzer finding hidden ORM iteration resource leaks inside loops."""
    def visit_For(self, node):
        orm_method = self.params.get("orm_method", "")
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if child.func.attr == orm_method:
                    self._add_finding("n_plus_one_query", child, 
                        f"Performance Alert: Database operations using '{orm_method}' detected inside a loop.")
        self.generic_visit(node)


class PiiLeakageVisitor(BaseOdoziVisitor):
    """Scans logger variables against dynamic compliance blacklists."""
    def visit_Call(self, node):
        logging_method = self.params.get("logging_method", "")
        sensitive_keywords = self.params.get("sensitive_keywords", "").split("|")
        
        is_log = False
        if isinstance(node.func, ast.Name) and node.func.id == logging_method:
            is_log = True
        elif isinstance(node.func, ast.Attribute) and node.func.attr == logging_method:
            is_log = True
            
        if is_log:
            for arg in node.args:
                arg_name = ""
                if isinstance(arg, ast.Name):
                    arg_name = arg.id
                elif isinstance(arg, ast.Keyword):
                    arg_name = arg.arg
                    
                if any(key.lower() in arg_name.lower() for key in sensitive_keywords if key):
                    self._add_finding("pii_leakage", node, 
                        f"Potential PII Leak: Sensitive key structure passed to {logging_method}.")
        self.generic_visit(node)
