import ast

class APIAuthVisitor(ast.NodeVisitor):

    def __init__(self, rule):

        self.rule = rule

        self.findings = []

    def visit_ClassDef(self, node):

        is_api_view = False

        for base in node.bases:

            if (
                isinstance(base, ast.Name)
                and "APIView" in base.id
            ):
                is_api_view = True

        if not is_api_view:
            return

        has_auth = False

        required = self.rule["required_auth"]

        for child in node.body:

            if isinstance(child, ast.Assign):

                for target in child.targets:

                    if (
                        isinstance(target, ast.Name)
                        and target.id == "permission_classes"
                    ):

                        if required in ast.unparse(child.value):
                            has_auth = True

        if not has_auth:

            self.findings.append({
                "type": "missing_authentication",
                "class": node.name,
                "required": required,
                "line": node.lineno
            })



class GeneralAuthenticationVisitor(ast.NodeVisitor):
    """Upgraded full authentication checker supporting functions and classes (views.py)."""
    def __init__(self, rule):
        self.rule = rule
        self.findings = []

    def visit_FunctionDef(self, node):
        target = self.rule.get("target", {})
        constraints = self.rule.get("constraints", {})
        prefix = target.get("function_prefix", "")
        decorator_name = constraints.get("decorator_name", "login_required")

        if prefix and not node.name.lower().startswith(prefix.lower()):
            return

        has_auth = any(getattr(dec, "id", None) == decorator_name for dec in node.decorator_list)
        if not has_auth:
            self.findings.append({
                "type": "missing_function_auth",
                "function": node.name,
                "required": decorator_name,
                "line": node.lineno
            })

    def visit_ClassDef(self, node):
        target = self.rule.get("target", {})
        prefix = target.get("function_prefix", "")
        if prefix and not node.name.lower().startswith(prefix.lower()):
            return

        auth_found = False
        AUTH_BASES = {"LoginRequiredMixin", "IsAuthenticated", "TokenAuthentication", "SessionAuthentication", "JWTAuthentication"}
        
        for base in node.bases:
            if getattr(base, "id", None) in AUTH_BASES:
                auth_found = True
                break

        if not auth_found:
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    for t in statement.targets:
                        if getattr(t, "id", "") in {"permission_classes", "authentication_classes"}:
                            auth_found = True
                            break
                if auth_found:
                    break

        if not auth_found:
            self.findings.append({
                "type": "missing_class_auth",
                "class": node.name,
                "line": node.lineno
            })

# ast.NodeVisitor allows us to walk through Python code as a tree
class FunctionConstraintVisitor(ast.NodeVisitor):
    """Checks functions for specific method wrappers like transaction.atomic."""
    def __init__(self, rule):
        self.rule = rule
        self.findings = []

    def visit_FunctionDef(self, node):
        target = self.rule.get("target", {})
        constraints = self.rule.get("constraints", {})
        
        keyword = target.get("name_contains", "")
        required_call = constraints.get("must_call", "atomic")  # Default to atomic

        # Only apply a name filter IF the user explicitly asked for one
        if keyword and keyword.lower() not in node.name.lower():
            return

        if required_call:
            found = False
            for child in ast.walk(node):
                if isinstance(child, ast.Attribute) and child.attr == required_call:
                    found = True
                elif isinstance(child, ast.Name) and child.id == required_call:
                    found = True

            if not found:
                self.findings.append({
                    "type": "missing_required_call",
                    "function": node.name,
                    "required": required_call,
                    "line": node.lineno
                })
        self.generic_visit(node)



class ClassLengthAndConstraintVisitor(ast.NodeVisitor):
    """
    Visitor for checking class constraints like maximum line length and required parent classes.
    
    Walks through Python AST and validates classes against configured rules.
    """

    def __init__(self, rule):
        """
        Initialize the ClassLengthAndConstraintVisitor.
        
        Args:
            rule: Configuration dict with 'target' and 'constraints' keys
        """

        self.rule = rule

        self.findings = []

    def visit_ClassDef(self, node):
        """
        Check class definition against configured constraints.
        
        Verifies that class inherits from required parent (if specified) 
        and does not exceed maximum allowed line count.
        
        Args:
            node: AST ClassDef node representing a class definition
        """

        # Extract target and constraints from the rule
        target = self.rule["target"]

        constraints = self.rule["constraints"]

        # Check if rule requires a specific parent class
        required_parent = target.get("inherits_from")

        if required_parent:
            found = False

            # Walk through class base classes to find required parent
            for base in node.bases:
                if (
                    isinstance(base, ast.Name)
                    and required_parent in base.id
                ):
                    found = True

            # Skip this class if required parent not found
            if not found:
                return

        # Check maximum line count constraint
        max_lines = constraints.get("max_lines")

        if max_lines:
            # Calculate total lines in class definition
            total = node.end_lineno - node.lineno

            # Report finding if class exceeds max allowed lines
            if total > max_lines:
                self.findings.append({
                    "type": "class_too_large",
                    "class": node.name,
                    "lines": total,
                    "max_allowed": max_lines
                })



class FunctionLengthVisitor(ast.NodeVisitor):
    """
    Checks function lengths, with optional filtering by function name 
    and the parent class of its containing class.
    """

    def __init__(self, rule):
        """
        Example Rule payload:
        {
          "target": {
            "inherits_from": "APIView",   # Only check functions inside APIView classes
            "name_contains": "post"       # Only check functions with 'post' in the name
          },
          "constraints": {
            "max_lines": 50
          }
        }
        """
        self.rule = rule
        self.findings = []
        self._current_class_parents = []  # Tracks inheritance context

    def visit_ClassDef(self, node):
        """Track the inheritance of the current class being walked."""
        # Extract parent names for the class we are currently inside
        parents = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                parents.append(base.id)
            elif isinstance(base, ast.Attribute):
                parents.append(base.attr)
        
        # Save context, walk child nodes (functions), then clear context
        old_parents = self._current_class_parents
        self._current_class_parents = parents
        
        self.generic_visit(node)
        
        self._current_class_parents = old_parents

    def visit_FunctionDef(self, node):
        target = self.rule.get("target", {})
        constraints = self.rule.get("constraints", {})
        
        required_parent = target.get("inherits_from")
        keyword = target.get("name_contains")
        max_lines = constraints.get("max_lines")

        # 1. Filter by Class Inheritance (if specified in the rule)
        if required_parent and required_parent not in self._current_class_parents:
            return

        # 2. Filter by Function Name Keyword (if specified in the rule)
        if keyword and keyword.lower() not in node.name.lower():
            return

        # 3. Assert Max Line Constraint
        if max_lines:
            total_lines = node.end_lineno - node.lineno
            if total_lines > max_lines:
                self.findings.append({
                    "type": "function_too_large",
                    "function": node.name,
                    "lines": total_lines,
                    "max_allowed": max_lines,
                    "line": node.lineno
                })
        
        self.generic_visit(node)




class DocstringConstraintVisitor(ast.NodeVisitor):
    """
    Visitor for checking documentation coverage on classes and functions.
    Matches the 'ast' batch rule-first structure.
    """

    def __init__(self, rule):
        """
        Example Rule payload:
        {
          "target": {
            "name_contains": ""  # Can leave empty to check all, or target specific names
          },
          "constraints": {
            "require_docstring": True
          }
        }
        """
        self.rule = rule
        self.findings = []

    def visit_FunctionDef(self, node):
        target = self.rule.get("target", {})
        constraints = self.rule.get("constraints", {})
        keyword = target.get("name_contains", "")

        # Skip private helper methods if needed, or filter by keyword
        if keyword and keyword.lower() not in node.name.lower():
            return

        if constraints.get("require_docstring"):
            # ast.get_docstring returns None if no docstring is present
            if ast.get_docstring(node) is None:
                self.findings.append({
                    "type": "missing_docstring",
                    "element": "function",
                    "name": node.name,
                    "line": node.lineno
                })
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        target = self.rule.get("target", {})
        constraints = self.rule.get("constraints", {})
        keyword = target.get("name_contains", "")

        if keyword and keyword.lower() not in node.name.lower():
            return

        if constraints.get("require_docstring"):
            if ast.get_docstring(node) is None:
                self.findings.append({
                    "type": "missing_docstring",
                    "element": "class",
                    "name": node.name,
                    "line": node.lineno
                })
        self.generic_visit(node)

            

class ErrorHandlingConstraintVisitor(ast.NodeVisitor):
    """Checks if specific risky calls are wrapped safely inside try/except blocks."""
    def __init__(self, rule):
        """
        Example Rule:
        {
          "target": { "risky_call": "send_payment" },
          "constraints": { "must_handle_errors": True }
        }
        """
        self.rule = rule
        self.findings = []

    def visit_Call(self, node):
        risky_call = self.rule.get("target", {}).get("risky_call", "")
        is_target_call = False
        
        if isinstance(node.func, ast.Name) and node.func.id == risky_call:
            is_target_call = True
        elif isinstance(node.func, ast.Attribute) and node.func.attr == risky_call:
            is_target_call = True
            
        if is_target_call:
            if not hasattr(node, '_in_try') or not node._in_try:
                self.findings.append({
                    "type": "missing_try_except_request",
                    "call": risky_call,
                    "line": node.lineno
                })
        self.generic_visit(node)

    def visit_Try(self, node):
        for child in ast.walk(node):
            child._in_try = True
        self.generic_visit(node)


class NPlusOneQueryConstraintVisitor(ast.NodeVisitor):
    """Detects dangerous database ORM methods executed within loop blocks."""
    def __init__(self, rule):
        """
        Example Rule:
        {
          "target": { "orm_method": "create" },
          "constraints": { "block_in_loops": True }
        }
        """
        self.rule = rule
        self.findings = []

    def visit_For(self, node):
        orm_method = self.rule.get("target", {}).get("orm_method", "")
        if orm_method:
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    if child.func.attr == orm_method:
                        self.findings.append({
                            "type": "n_plus_one_query",
                            "method": orm_method,
                            "line": child.lineno
                        })
        self.generic_visit(node)



class PiiLeakageConstraintVisitor(ast.NodeVisitor):
    """Scans logging statements to ensure blacklisted fields aren't outputted."""
    def __init__(self, rule):
        self.rule = rule
        self.findings = []

    def visit_Call(self, node):
        # Extract configuration keys from your unified layout structure
        target = self.rule.get("target", {})
        constraints = self.rule.get("constraints", {})
        
        logging_method = target.get("logging_method", "")
        sensitive_keywords = constraints.get("sensitive_keywords", "").split("|")
        
        # Determine if this specific function call is our target logger
        is_log = False
        if isinstance(node.func, ast.Name) and node.func.id == logging_method:
            is_log = True
        elif isinstance(node.func, ast.Attribute):
            # ast.unparse securely handles paths like 'logger.info' or 'self.logger.warn'
            full_call_path = ast.unparse(node.func)
            if logging_method in full_call_path:
                is_log = True
            
        if is_log:
            # 1. Scan positional arguments (e.g., logger.info(user_password))
            for arg in node.args:
                arg_text = ast.unparse(arg)
                if any(key.lower() in arg_text.lower() for key in sensitive_keywords if key):
                    self.findings.append({
                        "type": "pii_leakage",
                        "method": logging_method,
                        "variable": arg_text,
                        "line": node.lineno
                    })
                    
            # 2. Scan keyword arguments (e.g., logger.info("auth error", token=user_token))
            for kwarg in node.keywords:
                # We build a string combining the kwarg name (key) and its passed value
                kwarg_text = f"{kwarg.arg}={ast.unparse(kwarg.value)}"
                if any(key.lower() in kwarg_text.lower() for key in sensitive_keywords if key):
                    self.findings.append({
                        "type": "pii_leakage",
                        "method": logging_method,
                        "variable": kwarg_text,
                        "line": node.lineno
                    })

        # Keep traversing deeper down into the AST tree
        self.generic_visit(node)




# payloads
# {
#   "APIAuthVisitor": {
#     "target": {
#       "inherits_from": "APIView"
#     },
#     "constraints": {
#       "required_auth": "IsAuthenticated"
#     }
#   },
#   "GeneralAuthenticationVisitor_Functions": {
#     "target": {
#       "name_contains": "api_"
#     },
#     "constraints": {
#       "decorator_name": "login_required"
#     }
#   },
#   "GeneralAuthenticationVisitor_Classes": {
#     "target": {
#       "name_contains": "View"
#     },
#     "constraints": {
#       "decorator_name": "JWTAuthentication"
#     }
#   },
#   "FunctionConstraintVisitor_Atomic": {
#     "target": {
#       "name_contains": "save"
#     },
#     "constraints": {
#       "must_call": "atomic"
#     }
#   },
#   "FunctionConstraintVisitor_Required": {
#     "target": {
#       "name_contains": "process"
#     },
#     "constraints": {
#       "must_call": "validate_payload"
#     }
#   },
#   "ClassLengthVisitor": {
#     "target": {
#       "inherits_from": "Model"
#     },
#     "constraints": {
#       "max_lines": 150
#     }
#   },
#   "FunctionLengthVisitor": {
#     "target": {
#       "inherits_from": "APIView",
#       "name_contains": "post"
#     },
#     "constraints": {
#       "max_lines": 50
#     }
#   },
#   "DocstringConstraintVisitor": {
#     "target": {},
#     "constraints": {
#       "require_docstring": true
#     }
#   },
#   "ErrorHandlingConstraintVisitor": {
#     "target": {
#       "risky_call": "send_payment"
#     },
#     "constraints": {
#       "must_handle_errors": true
#     }
#   },
#   "NPlusOneQueryConstraintVisitor": {
#     "target": {
#       "orm_method": "create"
#     },
#     "constraints": {
#       "block_in_loops": true
#     }
#   },
#   "PiiLeakageConstraintVisitor": {
#     "target": {
#       "logging_method": "logger.info"
#     },
#     "constraints": {
#       "sensitive_keywords": "password|ssn|secret|token"
#     }
#   }
# }

