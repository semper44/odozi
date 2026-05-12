import ast


class TransactionAtomicVisitor(ast.NodeVisitor):

    def __init__(self, rule):
        self.rule = rule
        self.findings = []

    def visit_FunctionDef(self, node):

        keyword = self.rule["function_contains"]

        required = self.rule["required_call"]

        if keyword not in node.name.lower():
            return

        found = False

        for child in ast.walk(node):

            if (
                isinstance(child, ast.Attribute)
                and child.attr == required
            ):
                found = True

        if not found:

            self.findings.append({
                "type": "missing_required_call",
                "function": node.name,
                "required": required,
                "line": node.lineno
            })

        self.generic_visit(node)

class QueryOptimizationVisitor(ast.NodeVisitor):

    def __init__(self, rule):

        self.rule = rule

        self.findings = []

    def visit_For(self, node):

        required = self.rule["required_optimization"]

        for child in ast.walk(node):

            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
            ):

                attr = child.func.attr

                if attr == "all":

                    query_has_optimization = False

                    current = child.func.value

                    while isinstance(current, ast.Call):

                        if (
                            isinstance(current.func, ast.Attribute)
                            and current.func.attr == required
                        ):
                            query_has_optimization = True

                        current = current.func.value

                    if not query_has_optimization:

                        self.findings.append({
                            "type": "missing_query_optimization",
                            "required": required,
                            "line": child.lineno
                        })

        self.generic_visit(node)

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

class SerializerLengthVisitor(ast.NodeVisitor):

    def __init__(self, rule):

        self.rule = rule

        self.findings = []

    def visit_ClassDef(self, node):

        is_serializer = False

        for base in node.bases:

            if (
                isinstance(base, ast.Name)
                and "Serializer" in base.id
            ):
                is_serializer = True

        if not is_serializer:
            return

        start = node.lineno

        end = node.end_lineno

        total = end - start

        limit = self.rule["max_lines"]

        if total > limit:

            self.findings.append({
                "type": "serializer_too_large",
                "class": node.name,
                "lines": total,
                "max_allowed": limit,
                "line": node.lineno
            })

import ast


# ast.NodeVisitor allows us to walk through Python code as a tree
class FunctionConstraintVisitor(ast.NodeVisitor):

    def __init__(self, rule):

        """

        Constructor
        Receives ONE rule dynamically defined by the LLM.       

        Example:       

        {
          "target": {
            "name_contains": "payment"
          },
          "constraints": {
              "must_call": "atomic"
          }
        }

        """

        # Store the rule so it can be used later
        self.rule = rule

        # All findings/errors will be stored here
        self.findings = []


    # visit_FunctionDef automatically runs
    # every time AST finds a function
    #
    # Example:
    #
    # def process_payment():
    #     pass
    #
    def visit_FunctionDef(self, node):

        # Extract "target" section from rule
        # {
        #   "name_contains": "payment"
        # }
        target = self.rule["target"]

        # Extract "constraints" section
        # {
        #   "must_call": "atomic"
        # }
        constraints = self.rule["constraints"]



        # Get the keyword we want to match Example:"payment"
        keyword = target.get("name_contains")


        # Only continue if keyword exists
        if keyword:

            # node.name is the function name
            # Example:
            # process_payment
            if keyword not in node.name.lower():
                return



        # Get required method/function call
        #
        # Example:
        # "atomic"
        #
        required_call = constraints.get("must_call")


        # Only continue if rule requires a call
        if required_call:

            # Assume function DOES NOT contain required call
            found = False


            # ast.walk(node)
            #
            # Walks through EVERYTHING inside the function
            #
            # Example:
            #
            # def process_payment():
            #     with transaction.atomic():
            #         save()
            #
            for child in ast.walk(node):


                # ast.Attribute means:
                #
                # something.something
                #
                # Example:
                # transaction.atomic
                #
                if (
                    isinstance(child, ast.Attribute)

                    # attr is the RIGHT side
                    #
                    # transaction.atomic
                    #             ^^^^^^
                    #
                    and child.attr == required_call
                ):

                    # Required call found
                    found = True


            # If required call was NEVER found
            if not found:

                # Save finding
                self.findings.append({

                    # Type of issue
                    "type": "missing_required_call",

                    # Function name
                    "function": node.name,

                    # What should have existed
                    "required": required_call,

                    # Line number in file
                    "line": node.lineno
                })


        # Continue walking deeper into AST tree
        self.generic_visit(node)


class ClassLengthVisitor(ast.NodeVisitor):

    def __init__(self, rule):

        self.rule = rule

        self.findings = []

    def visit_ClassDef(self, node):

        target = self.rule["target"]

        constraints = self.rule["constraints"]

        required_parent = target.get("inherits_from")

        if required_parent:

            found = False

            for base in node.bases:

                if (
                    isinstance(base, ast.Name)
                    and required_parent in base.id
                ):
                    found = True

            if not found:
                return

        max_lines = constraints.get("max_lines")

        if max_lines:

            total = node.end_lineno - node.lineno

            if total > max_lines:

                self.findings.append({
                    "type": "class_too_large",
                    "class": node.name,
                    "lines": total,
                    "max_allowed": max_lines
                })

            