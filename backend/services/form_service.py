"""
Dynamic Form Engine Service
Handles form CRUD, field management, response submission, and validation
"""
import json
from datetime import datetime
from typing import Optional
from models import db
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class FormService:

    @staticmethod
    def create_form(factory_id: int, user_id: int, data: dict) -> dict:
        sql = """
            INSERT INTO forms (name, description, module, factory_id, is_active, version)
            VALUES (:name, :description, :module, :factory_id, TRUE, 1)
            RETURNING id, name, module, factory_id, version, created_at
        """
        row = db.session.execute(text(sql), {
            "name": data["name"],
            "description": data.get("description", ""),
            "module": data.get("module", "inspection"),
            "factory_id": factory_id,
        }).fetchone()
        form_id = row.id

        # Insert fields
        for idx, field in enumerate(data.get("fields", [])):
            db.session.execute(text("""
                INSERT INTO form_fields
                    (form_id, label, field_key, field_type, is_required, order_index,
                     validation_rules, options, conditional_logic, calculation_formula, placeholder, help_text)
                VALUES
                    (:form_id, :label, :field_key, :field_type, :is_required, :order_index,
                     :validation_rules, :options, :conditional_logic, :calculation_formula, :placeholder, :help_text)
            """), {
                "form_id": form_id,
                "label": field["label"],
                "field_key": field.get("field_key", field["label"].lower().replace(" ", "_")),
                "field_type": field.get("field_type", "text"),
                "is_required": field.get("is_required", False),
                "order_index": field.get("order_index", idx),
                "validation_rules": json.dumps(field.get("validation_rules", {})),
                "options": json.dumps(field.get("options", [])),
                "conditional_logic": json.dumps(field.get("conditional_logic", {})),
                "calculation_formula": field.get("calculation_formula"),
                "placeholder": field.get("placeholder"),
                "help_text": field.get("help_text"),
            })

        db.session.commit()
        return FormService.get_form(form_id, factory_id)

    @staticmethod
    def get_forms(factory_id: int, module: Optional[str] = None) -> list:
        filters = ["f.factory_id = :factory_id", "f.deleted_at IS NULL"]
        params = {"factory_id": factory_id}
        if module:
            filters.append("f.module = :module")
            params["module"] = module

        sql = f"""
            SELECT f.id, f.name, f.description, f.module, f.is_active, f.version, f.created_at,
                   COUNT(ff.id) AS field_count,
                   COUNT(fr.id) AS response_count
            FROM forms f
            LEFT JOIN form_fields ff ON ff.form_id = f.id
            LEFT JOIN form_responses fr ON fr.form_id = f.id AND fr.deleted_at IS NULL
            WHERE {' AND '.join(filters)}
            GROUP BY f.id
            ORDER BY f.created_at DESC
        """
        rows = db.session.execute(text(sql), params).fetchall()
        return [dict(r._mapping) for r in rows]

    @staticmethod
    def get_form(form_id: int, factory_id: int) -> Optional[dict]:
        row = db.session.execute(text("""
            SELECT id, name, description, module, factory_id, is_active, version, created_at
            FROM forms WHERE id = :id AND factory_id = :factory_id AND deleted_at IS NULL
        """), {"id": form_id, "factory_id": factory_id}).fetchone()

        if not row:
            return None

        fields = db.session.execute(text("""
            SELECT id, label, field_key, field_type, is_required, order_index,
                   validation_rules, options, conditional_logic, calculation_formula,
                   placeholder, help_text
            FROM form_fields
            WHERE form_id = :form_id
            ORDER BY order_index
        """), {"form_id": form_id}).fetchall()

        form_dict = dict(row._mapping)
        form_dict["fields"] = [dict(f._mapping) for f in fields]
        return form_dict

    @staticmethod
    def submit_response(form_id: int, factory_id: int, user_id: int,
                        data: dict) -> dict:
        """Validate and store a form response."""
        form = FormService.get_form(form_id, factory_id)
        if not form:
            raise ValueError("Form not found")
        if not form["is_active"]:
            raise ValueError("Form is not active")

        # Validate required fields and compute calculated fields
        errors = []
        response_data = dict(data)

        for field in form["fields"]:
            key = field["field_key"]
            val = data.get(key)

            if field["is_required"] and (val is None or val == ""):
                errors.append(f"Field '{field['label']}' is required")
                continue

            # Compute calculated fields
            if field["field_type"] == "calculated" and field["calculation_formula"]:
                try:
                    formula = field["calculation_formula"]
                    # Safe eval with limited scope
                    calc_val = eval(formula, {"__builtins__": {}}, response_data)
                    response_data[key] = round(float(calc_val), 4) if calc_val else 0
                except Exception as e:
                    logger.warning(f"Calculation failed for {key}: {e}")

            # Validate number ranges
            if field["field_type"] == "number" and val is not None:
                rules = field.get("validation_rules") or {}
                if isinstance(rules, str):
                    rules = json.loads(rules) if rules else {}
                if "min" in rules and float(val) < float(rules["min"]):
                    errors.append(f"Field '{field['label']}' must be ≥ {rules['min']}")
                if "max" in rules and float(val) > float(rules["max"]):
                    errors.append(f"Field '{field['label']}' must be ≤ {rules['max']}")

        if errors:
            raise ValueError(f"Validation errors: {'; '.join(errors)}")

        row = db.session.execute(text("""
            INSERT INTO form_responses (form_id, user_id, factory_id, data, submitted_at)
            VALUES (:form_id, :user_id, :factory_id, :data, NOW())
            RETURNING id, form_id, submitted_at
        """), {
            "form_id": form_id,
            "user_id": user_id,
            "factory_id": factory_id,
            "data": json.dumps(response_data),
        }).fetchone()
        db.session.commit()

        return {
            "id": row.id,
            "form_id": row.form_id,
            "submitted_at": str(row.submitted_at),
            "data": response_data,
        }

    @staticmethod
    def get_responses(form_id: int, factory_id: int, limit: int = 100,
                      offset: int = 0) -> dict:
        total = db.session.execute(text("""
            SELECT COUNT(*) FROM form_responses
            WHERE form_id = :form_id AND factory_id = :factory_id AND deleted_at IS NULL
        """), {"form_id": form_id, "factory_id": factory_id}).scalar()

        rows = db.session.execute(text("""
            SELECT fr.id, fr.submitted_at, fr.data, u.name AS submitted_by
            FROM form_responses fr
            LEFT JOIN users u ON u.id = fr.user_id
            WHERE fr.form_id = :form_id AND fr.factory_id = :factory_id AND fr.deleted_at IS NULL
            ORDER BY fr.submitted_at DESC
            LIMIT :limit OFFSET :offset
        """), {"form_id": form_id, "factory_id": factory_id, "limit": limit, "offset": offset}).fetchall()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "responses": [dict(r._mapping) for r in rows],
        }

    @staticmethod
    def delete_form(form_id: int, factory_id: int) -> bool:
        """Soft delete."""
        result = db.session.execute(text("""
            UPDATE forms SET deleted_at = NOW()
            WHERE id = :id AND factory_id = :factory_id AND deleted_at IS NULL
        """), {"id": form_id, "factory_id": factory_id})
        db.session.commit()
        return result.rowcount > 0
