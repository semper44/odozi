# rules_library.py

LIBRARY = {
    "check_auth": """
rules:
  - id: odozi-missing-auth-decorator
    languages: [python]
    severity: ERROR
    message: "Critical: Function '$FUNC' is missing the @{decorator_name} decorator."
    patterns:
      - pattern: |
          def $FUNC(...):
              ...
      - pattern-not-inside: |
          @{decorator_name}
          def $FUNC(...):
              ...
      - metavariable-regex:
          metavariable: $FUNC
          regex: '^({function_prefix}).*'
""",

    "check_required_call": """
rules:
  - id: odozi-missing-required-call
    languages: [python]
    severity: ERROR
    message: "Function $FUNC matches keyword '{keyword}' but is missing the required '{required_call}' call."
    patterns:
      - pattern-regex: 'def .*(?i){keyword}.*\\(.*\\):'
      - pattern-not-inside: |
          def $FUNC(...):
              ...
              {required_call}(...)
              ...
""",

    "check_function_length": """
rules:
  - id: odozi-function-too-large
    languages: [python]
    severity: WARNING
    message: "Function $FUNC matches keyword '{keyword}' but exceeds the {max_lines}-line limit."
    patterns:
      - pattern: |
          def $FUNC(...):
              ...
      - metavariable-regex:
          metavariable: $FUNC
          regex: '(?i).*{keyword}.*'
      - metavariable-comparison:
          metavariable: $FUNC
          comparison: (int(value.end_line) - int(value.start_line)) > {max_lines}
""",

    "check_class_length": """
rules:
  - id: odozi-class-too-large
    languages: [python]
    severity: WARNING
    message: "Class $CLASS inherits from {parent_class} but exceeds the {max_lines}-line limit."
    patterns:
      - pattern: |
          class $CLASS(..., {parent_class}, ...):
              ...
      - metavariable-comparison:
          metavariable: $CLASS
          comparison: (int(value.end_line) - int(value.start_line)) > {max_lines}
""",

    "check_error_handling": """
rules:
  - id: odozi-missing-try-except-request
    languages: [python]
    severity: ERROR
    message: "Unsafe Execution: '{risky_call}' should be wrapped in a try/except block to handle execution failures."
    patterns:
      - pattern: '{risky_call}(...)'
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
    message: "Performance Alert: Database operations using '{orm_method}' detected inside a loop."
    patterns:
      - pattern-inside: |
          for $X in $Y:
              ...
      - pattern: '$MODEL.{orm_method}(...)'
""",

    "check_pii": """
rules:
  - id: odozi-pii-leakage
    languages: [python]
    severity: WARNING
    message: "Potential PII Leak: Variable $VAR might contain sensitive data and should not be passed to {logging_method}."
    patterns:
      - pattern: '{logging_method}(..., $VAR, ...)'
      - metavariable-regex:
          metavariable: $VAR
          regex: '(?i).*({sensitive_keywords}).*'
""",
}
