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


class AuthenticationVisitor(BaseOdoziVisitor):

    def visit_FunctionDef(self, node):

        prefix = self.params.get(
            "function_prefix",
            ""
        )

        decorator_name = self.params.get(
            "decorator_name",
            "login_required"
        )

        if (
            prefix
            and not node.name.lower().startswith(
                prefix.lower()
            )
        ):
            return

        has_auth_decorator = any(
            getattr(dec, "id", None)
            == decorator_name
            for dec in node.decorator_list
        )

        if not has_auth_decorator:
           self.findings.append(
                {
                    "rule": "missing_authentication",
                    "type": "function",
                    "name": node.name,
                    "line": node.lineno,
                    "message": (
                        f"Function '{node.name}' "
                        f"is missing {decorator_name}"
                    )
                }
            )

    def visit_ClassDef(self, node):
        prefix = self.params.get(
            "function_prefix",
            ""
        )

        # Only inspect classes matching the requested prefix
        if (
            prefix
            and not node.name.lower().startswith(
                prefix.lower()
            )
        ):
            return

        auth_found = False

        # --------------------------------------------------
        # Check inheritance
        # Example:
        # class CreateTask(LoginRequiredMixin, APIView):
        # --------------------------------------------------
        AUTH_BASES = {
            "LoginRequiredMixin",
            "IsAuthenticated",
            "TokenAuthentication",
            "SessionAuthentication",
            "JWTAuthentication",
        }

        for base in node.bases:

            base_name = getattr(base, "id", None)

            if base_name in AUTH_BASES:
                auth_found = True
                break

        # --------------------------------------------------
        # Check class attributes
        #
        # permission_classes = [IsAuthenticated]
        # authentication_classes = [JWTAuthentication]
        # --------------------------------------------------
        if not auth_found:

            for statement in node.body:

                if not isinstance(statement, ast.Assign):
                    continue

                for target in statement.targets:

                    target_name = getattr(
                        target,
                        "id",
                        ""
                    )

                    if target_name in {
                        "permission_classes",
                        "authentication_classes"
                    }:
                        auth_found = True
                        break

                if auth_found:
                    break

        # --------------------------------------------------
        # Report if no authentication mechanism found
        # --------------------------------------------------
        if not auth_found:

            self.findings.append(
                {
                    "rule": "missing_authentication",
                    "type": "class",
                    "name": node.name,
                    "line": node.lineno,
                    "message": (
                        f"Class '{node.name}' "
                        f"has no authentication configured"
                    )
                }
            )


    def analyze_file(
        self,
        file_path,
        source_code
    ):

        # Only analyze views.py

        if not file_path.endswith("views.py"):
            return []

        self.findings = []

        try:
            tree = ast.parse(source_code)

        except SyntaxError:
            return []

        self.visit(tree)

        return self.findings


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


