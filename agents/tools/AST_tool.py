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

        # Extract "constraints"
        constraints = self.rule["constraints"]

        # Get the keyword we want to match Example:"payment"
        keyword = target.get("name_contains")

        # Only continue if keyword exists
        if keyword:
            # check keyword in node.name, where node.name is the function name Example:process_payment
            if keyword not in node.name.lower():
                return
        # Get required constraints call that should exist inside the function Example:"atomic"
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
    """
    Visitor for checking class constraints like maximum line length and required parent classes.
    
    Walks through Python AST and validates classes against configured rules.
    """

    def __init__(self, rule):
        """
        Initialize the ClassLengthVisitor.
        
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


            