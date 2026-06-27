"""Output validation."""



from __future__ import annotations



import json

import re

from datetime import datetime

from typing import Any



import jsonschema



from runtime.exceptions import ValidationError





class OutputValidator:

    """Validate provider output against capability rules and schemas."""



    def validate(

        self,

        content: str,

        *,

        schema: dict[str, Any] | None,

        rules: dict[str, Any],

    ) -> Any:

        parsed = self._parse_content(content, rules)

        if rules.get("schema_validate", True) and schema is not None:

            errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(parsed), key=str)

            if errors:

                messages = [error.message for error in errors]

                raise ValidationError("Schema validation failed", errors=messages)



        self._validate_required_fields(parsed, rules)

        self._validate_enums(parsed, rules.get("enums", {}))

        self._validate_regex(parsed, rules.get("regex", {}))

        self._validate_lengths(parsed, rules.get("length", {}))

        self._validate_dates(parsed, rules.get("dates", {}))

        self._validate_confidence(parsed, rules.get("confidence", {}))

        return parsed



    def _parse_content(self, content: str, rules: dict[str, Any]) -> Any:

        expect_json = rules.get("schema_validate", True)

        if not expect_json:

            return content

        try:

            return json.loads(content)

        except json.JSONDecodeError as exc:

            raise ValidationError(f"Output is not valid JSON: {exc}") from exc



    def _validate_required_fields(self, parsed: Any, rules: dict[str, Any]) -> None:

        required_fields = rules.get("required_fields", [])

        if required_fields and isinstance(parsed, dict):

            missing = [field for field in required_fields if field not in parsed]

            if missing:

                raise ValidationError(

                    f"Missing required fields: {', '.join(missing)}",

                    errors=[f"missing:{field}" for field in missing],

                )



    def _validate_enums(self, parsed: Any, enums: dict[str, list[Any]]) -> None:

        if not isinstance(parsed, dict) or not enums:

            return

        errors: list[str] = []

        for field, allowed in enums.items():

            value = self._resolve_path(parsed, field)

            if value is None:

                continue

            if value not in allowed:

                errors.append(f"enum:{field}={value!r} not in {allowed}")

        if errors:

            raise ValidationError("Enum validation failed", errors=errors)



    def _validate_regex(self, parsed: Any, patterns: dict[str, str]) -> None:

        if not isinstance(parsed, dict) or not patterns:

            return

        errors: list[str] = []

        for field, pattern in patterns.items():

            value = self._resolve_path(parsed, field)

            if value is None or value == "":

                continue

            if not re.match(pattern, str(value)):

                errors.append(f"regex:{field}")

        if errors:

            raise ValidationError("Regex validation failed", errors=errors)



    def _validate_lengths(self, parsed: Any, lengths: dict[str, dict[str, int]]) -> None:

        if not isinstance(parsed, dict) or not lengths:

            return

        errors: list[str] = []

        for field, bounds in lengths.items():

            if field.endswith("[]"):

                base = field[:-2]

                values = parsed.get(base)

                if not isinstance(values, list):

                    continue

                min_items = bounds.get("min_items")

                max_items = bounds.get("max_items")

                if min_items is not None and len(values) < min_items:

                    errors.append(f"length:{field}:min_items")

                if max_items is not None and len(values) > max_items:

                    errors.append(f"length:{field}:max_items")

                continue



            value = self._resolve_path(parsed, field)

            if value is None:

                continue

            if isinstance(value, str):

                min_len = bounds.get("min")

                max_len = bounds.get("max")

                if min_len is not None and len(value) < min_len:

                    errors.append(f"length:{field}:min")

                if max_len is not None and len(value) > max_len:

                    errors.append(f"length:{field}:max")

        if errors:

            raise ValidationError("Length validation failed", errors=errors)



    def _validate_dates(self, parsed: Any, dates: dict[str, dict[str, str]]) -> None:

        if not isinstance(parsed, dict) or not dates:

            return

        errors: list[str] = []

        for field, spec in dates.items():

            if "[]" in field:

                base, leaf = field.split("[].", 1)

                items = parsed.get(base)

                if not isinstance(items, list):

                    continue

                for item in items:

                    if not isinstance(item, dict):

                        continue

                    value = item.get(leaf)

                    if value and not self._is_valid_date_token(str(value)):

                        errors.append(f"date:{field}")

            else:

                value = self._resolve_path(parsed, field)

                if value and not self._is_valid_date_token(str(value)):

                    errors.append(f"date:{field}")

        if errors:

            raise ValidationError("Date validation failed", errors=errors)



    def _validate_confidence(self, parsed: Any, confidence: dict[str, Any]) -> None:

        if not isinstance(parsed, dict) or not confidence:

            return

        min_overall = confidence.get("min_overall")

        if min_overall is not None:

            overall = parsed.get("confidence")

            if overall is not None and float(overall) < float(min_overall):

                raise ValidationError(

                    f"Confidence below threshold: {overall} < {min_overall}",

                    errors=[f"confidence:overall<{min_overall}"],

                )



        field_thresholds = confidence.get("field_thresholds", {})

        errors: list[str] = []

        for field, threshold in field_thresholds.items():

            value = self._resolve_path(parsed, field)

            if value is None:

                continue

            if isinstance(value, (int, float)) and float(value) < float(threshold):

                errors.append(f"confidence:{field}<{threshold}")

        if errors:

            raise ValidationError("Field confidence validation failed", errors=errors)



    def _resolve_path(self, data: dict[str, Any], path: str) -> Any:

        current: Any = data

        for part in path.split("."):

            if not isinstance(current, dict):

                return None

            current = current.get(part)

        return current



    def _is_valid_date_token(self, value: str) -> bool:

        if value.lower() in {"present", "current", "now"}:

            return True

        for fmt in ("%Y-%m", "%Y-%m-%d", "%Y"):

            try:

                datetime.strptime(value, fmt)

                return True

            except ValueError:

                continue

        return False

