# -*- coding: utf-8 -*-
"""
Lead Magnet Capture Controller — Nextdoo Cloud.

Endpoint público para capturar leads desde landings de recursos
(calculadora ROI, calculadora costes, checklists, guías, etc).

POST /api/lead-magnet  (JSON-in, JSON-out, CORS open)

Crea un crm.lead etiquetado, lo asigna al CEO, programa una actividad
de llamada con deadline HOY y notifica al admin por email + bus.
"""

import json
import logging
from datetime import datetime

from odoo import http, fields, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# CEO / admin comercial que recibe los leads (Jeanlouis Rodes).
# Fallback: primer usuario con grupo sales_manager.
DEFAULT_ASSIGNEE_LOGIN = "jeanlouis"

# Dominios permitidos para CORS.
CORS_ALLOWED_ORIGINS = {
    "https://www.nextdoo.cloud",
    "https://nextdoo.cloud",
    "https://supportboo.github.io",
    "https://www.boomatik.com",
    "https://boomatik.com",
    # development
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
}

# Lead magnets conocidos → tag base.
SOURCE_TAGS = {
    "roi-calculator":      ["ROI Calculator", "Lead Magnet"],
    "cost-calculator":     ["Cost Calculator", "Lead Magnet"],
    "migration-checklist": ["Migration Checklist", "Lead Magnet"],
    "retail-guide":        ["Retail Guide", "Lead Magnet"],
    "demo-request":        ["Demo Request"],
    "consultation-request":["Consultation Request"],
}


def _cors_headers(origin):
    allow = origin if origin in CORS_ALLOWED_ORIGINS else "https://www.nextdoo.cloud"
    return [
        ("Access-Control-Allow-Origin", allow),
        ("Access-Control-Allow-Methods", "POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
        ("Access-Control-Max-Age", "3600"),
        ("Vary", "Origin"),
    ]


def _json_response(data, status=200, origin=""):
    headers = _cors_headers(origin) + [("Content-Type", "application/json; charset=utf-8")]
    return Response(json.dumps(data, ensure_ascii=False), status=status, headers=headers)


class LeadMagnetController(http.Controller):

    @http.route(
        "/api/lead-magnet",
        type="http",
        auth="public",
        methods=["POST", "OPTIONS"],
        csrf=False,
        save_session=False,
    )
    def capture(self, **kwargs):
        origin = request.httprequest.headers.get("Origin", "")

        # CORS preflight
        if request.httprequest.method == "OPTIONS":
            return Response("", status=204, headers=_cors_headers(origin))

        # Parse JSON body
        try:
            raw = request.httprequest.get_data(as_text=True) or "{}"
            data = json.loads(raw)
        except Exception as e:
            _logger.warning("lead-magnet: invalid JSON: %s", e)
            return _json_response({"ok": False, "error": "invalid_json"}, 400, origin)

        # Validate required
        email = (data.get("email_from") or data.get("email") or "").strip()
        name = (data.get("name") or data.get("nombre") or "").strip()
        if not email or "@" not in email or not name:
            return _json_response({"ok": False, "error": "missing_fields"}, 400, origin)

        empresa = (data.get("partner_name") or data.get("empresa") or name).strip()
        phone = (data.get("phone") or data.get("telefono") or "").strip()
        cargo = (data.get("function") or data.get("cargo") or "").strip()
        description = data.get("description") or self._format_description(data)
        source = (data.get("source") or "lead-magnet").strip()
        timeline = (data.get("urgency") or data.get("timeline") or "6m").strip()
        # Tier del lead magnet:
        #   meeting  → sesión 1-1 con CEO (lead caliente, contacto HOY)
        #   email    → solo análisis por email (lead exploratorio, follow-up 48 h)
        tier = (data.get("tier") or "meeting").strip().lower()
        if tier not in ("meeting", "email"):
            tier = "meeting"

        env = request.env(su=True)
        try:
            # 1. Resolve assignee
            assignee = env["res.users"].search(
                [("login", "=", DEFAULT_ASSIGNEE_LOGIN)], limit=1
            )
            if not assignee:
                assignee = env.ref("base.user_admin", raise_if_not_found=False)
            if not assignee:
                assignee = env["res.users"].search([("share", "=", False)], limit=1)

            # 2. Resolve/create tags (añadimos tag por tier)
            tag_names = list(SOURCE_TAGS.get(source, ["Lead Magnet"]))
            if tier == "meeting":
                tag_names.append("Meeting Request")
                tag_names.append("Hot Lead")
            else:
                tag_names.append("Email-only")
                tag_names.append("Cold Lead")
            if data.get("tags"):
                for t in data["tags"]:
                    if t and t not in tag_names:
                        tag_names.append(t)
            tag_ids = self._upsert_tags(env, tag_names)

            # 3. Resolve sales team (Nextdoo default)
            team = env["crm.team"].search([("company_id", "=", env.company.id)], limit=1)

            # 4. Priority — tier meeting siempre 3★ (lead caliente),
            #    tier email se rige por urgencia declarada (suele ser baja).
            if tier == "meeting":
                priority = "3" if timeline in ("3m", "6m") else "2"
            else:
                priority_map = {"3m": "2", "6m": "1", "12m": "1", "explorar": "0"}
                priority = priority_map.get(timeline, "1")

            # 5. Create lead — nombre prefijado con tier para que se vea en el listado CRM
            tier_label = "[1-1] " if tier == "meeting" else "[email] "
            lead_vals = {
                "name": f"{tier_label}{source} · {empresa}",
                "contact_name": name,
                "partner_name": empresa,
                "email_from": email,
                "phone": phone,
                "function": cargo,
                "description": description,
                "tag_ids": [(6, 0, tag_ids)],
                "user_id": assignee.id if assignee else False,
                "team_id": team.id if team else False,
                "priority": priority,
                "type": "lead",
                "source_id": False,
                "medium_id": False,
            }
            lead = env["crm.lead"].create(lead_vals)

            # 6. Create activity diferenciada por tier
            if tier == "meeting":
                # Lead caliente: LLAMADA hoy mismo
                activity_type = env.ref(
                    "mail.mail_activity_data_call", raise_if_not_found=False
                ) or env.ref(
                    "mail.mail_activity_data_todo", raise_if_not_found=False
                )
                summary = f"[HOY · 1-1] Llamar a {name} ({empresa}) — sesión solicitada"
                note = (
                    f"<p><b>Lead caliente · solicita sesión 1-1 con CEO.</b></p>"
                    f"<p>Tlf: <b>{phone}</b> · Email: {email}</p>"
                    f"<p>Urgencia: <b>{timeline}</b></p>"
                    f"<p>Acción: confirmar hueco hoy mismo y enviar invite de calendar.</p>"
                )
                deadline = fields.Date.context_today(env["mail.activity"])
            else:
                # Lead frío: enviar email primero, follow-up 48 h
                activity_type = env.ref(
                    "mail.mail_activity_data_email", raise_if_not_found=False
                ) or env.ref(
                    "mail.mail_activity_data_todo", raise_if_not_found=False
                )
                summary = f"[Follow-up] Email {email} · ofrecer upgrade a sesión 1-1"
                note = (
                    f"<p>Lead descargó análisis básico por email.</p>"
                    f"<p>Enviar PDF con KPIs + invitación a sesión 1-1 con CEO.</p>"
                    f"<p>Si no responde en 48 h, marcar como lost o reactivar con caso de éxito sector.</p>"
                )
                deadline = fields.Date.add(
                    fields.Date.context_today(env["mail.activity"]), days=2
                )

            if activity_type:
                env["mail.activity"].create({
                    "res_model_id": env["ir.model"]._get("crm.lead").id,
                    "res_id": lead.id,
                    "activity_type_id": activity_type.id,
                    "summary": summary,
                    "note": note,
                    "date_deadline": deadline,
                    "user_id": assignee.id if assignee else env.user.id,
                })

            # 7. Post message in lead chatter (visible in CRM)
            lead.message_post(
                body=(
                    f"<p><b>Nuevo lead {tier} vía {source}.</b></p>"
                    f"<pre style='font-family:monospace;white-space:pre-wrap'>{description}</pre>"
                ),
                subtype_xmlid="mail.mt_note",
            )

            # 8. Send email notification to CEO (interno)
            try:
                template = env.ref(
                    "nextdoo_lead_capture.mail_template_lead_notification",
                    raise_if_not_found=False,
                )
                if template and assignee:
                    template.with_context(
                        lead_source=source,
                        lead_urgency=timeline,
                        lead_tier=tier,
                    ).send_mail(lead.id, force_send=True)
            except Exception as e:
                _logger.warning("lead-magnet: email notif failed: %s", e)

            # 9. Enviar análisis básico al lead (solo tier email)
            if tier == "email":
                try:
                    customer_tpl = env.ref(
                        "nextdoo_lead_capture.mail_template_roi_summary_customer",
                        raise_if_not_found=False,
                    )
                    if customer_tpl:
                        customer_tpl.send_mail(lead.id, force_send=True)
                except Exception as e:
                    _logger.warning("lead-magnet: customer email failed: %s", e)

            return _json_response(
                {"ok": True, "lead_id": lead.id, "source": source, "tier": tier}, 200, origin
            )

        except Exception as e:
            _logger.exception("lead-magnet: capture failed")
            return _json_response(
                {"ok": False, "error": "server_error", "msg": str(e)}, 500, origin
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _upsert_tags(env, names):
        ids = []
        for n in names:
            n = (n or "").strip()
            if not n:
                continue
            tag = env["crm.tag"].search([("name", "=ilike", n)], limit=1)
            if not tag:
                tag = env["crm.tag"].create({"name": n})
            ids.append(tag.id)
        return ids

    @staticmethod
    def _format_description(data):
        """Si no llega description, la construimos a partir del payload."""
        analysis = data.get("analysis") or {}
        lines = [
            "=== LEAD MAGNET CAPTURE ===",
            f"Empresa: {data.get('empresa') or data.get('partner_name') or '—'}",
            f"Contacto: {data.get('nombre') or data.get('name') or '—'} ({data.get('cargo') or data.get('function') or '—'})",
            f"Email: {data.get('email') or data.get('email_from') or '—'}",
            f"Teléfono: {data.get('telefono') or data.get('phone') or '—'}",
            f"Fuente: {data.get('source') or '—'}",
            f"Urgencia: {data.get('urgency') or data.get('timeline') or '—'}",
            "",
            "--- ANÁLISIS ---",
        ]
        for k, v in (analysis or {}).items():
            lines.append(f"{k}: {v}")
        lines += [
            "",
            "=== ACCIÓN ===",
            "Contactar HOY. Llamada o videoconf en 24 h.",
            f"Timestamp: {data.get('timestamp') or datetime.utcnow().isoformat()}",
        ]
        return "\n".join(lines)
