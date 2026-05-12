LIBRARY = {
    "check_auth": """
rules:
  - id: odozi-missing-auth-decorator
    languages: [python]
    severity: ERROR
    message: "Critical: Function '$FUNC' is missing the @login_required decorator."
    patterns:
      - pattern: |
          def $FUNC(...):
              ...
      - pattern-not-inside: |
          @login_required
          def $FUNC(...):
              ...
      - metavariable-regex:
          metavariable: $FUNC
          regex: ^(post_|api_).*
""",

    "check_required_call": """
rules:
  - id: odozi-missing-required-call
    languages: [python]
    severity: ERROR
    message: "Function $FUNC matches keyword 'payment' but is missing the required 'atomic' call."
    patterns:
      # 1. Target functions with the keyword in the name
      - pattern-regex: def .*(?i)payment.*\(.*\):
      # 2. Filter out functions that DO have the required call
      - pattern-not-inside: |
          def $FUNC(...):
              ...
              transaction.atomic(...)
              ...
""",

    "check_class_length": """
rules:
  - id: odozi-class-too-large
    languages: [python]
    severity: WARNING
    message: "Class $CLASS inherits from BaseClassName but exceeds the 100-line limit."
    patterns:
      # 1. Target classes inheriting from a specific parent
      - pattern: |
          class $CLASS(..., BaseClassName, ...):
              ...
      # 2. Calculate the line delta
      - metavariable-comparison:
          metavariable: $CLASS
          comparison: (int(value.end_line) - int(value.start_line)) > 100
""",

    "check_error_handling": """
rules:
  - id: odozi-missing-try-except-request
    languages: [python]
    severity: ERROR
    message: "Unsafe Request: 'requests.post' should be wrapped in a try/except block to handle network failures."
    patterns:
      - pattern: requests.post(...)
      - pattern-not-inside: |
          try:
              ...
          except ...:
              ...
""",

    "check_n_plus_one": """
rules:
  - id: odozi-n-plus-one-query
    languages: [python]
    severity: WARNING
    message: "Performance Alert: Database query detected inside a loop. Consider using select_related() or bulk_create()."
    patterns:
      - pattern-inside: |
          for $X in $Y:
              ...
      - pattern-either:
          - pattern: $MODEL.objects.get(...)
          - pattern: $MODEL.objects.filter(...)
          - pattern: $MODEL.objects.create(...)
""",

    "check_pii": """
rules:
  - id: odozi-pii-leakage
    languages: [python]
    severity: WARNING
    message: "Potential PII Leak: Variable $VAR might contain sensitive data and should not be logged."
    patterns:
      - pattern-either:
          - pattern: logger.info(..., $VAR, ...)
          - pattern: print(..., $VAR, ...)
      - metavariable-regex:
          metavariable: $VAR
          regex: (?i).*(password|secret|token|email|ssn).*
""",
}
