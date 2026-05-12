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

# CEO / admin comercial que recibe los leads por defecto (Jeanlouis Rodes).
DEFAULT_ASSIGNEE_LOGIN = "jeanlouis"

# Routing por landing/source · qué comercial atiende cada tipo de lead magnet.
# Cualquier source no listado cae al DEFAULT_ASSIGNEE_LOGIN.
ASSIGNEE_BY_SOURCE = {
    "roi-calculator":      "jeanlouis",   # CEO maneja ROI (lead caliente)
    "cost-calculator":     "gabrielrm",   # Gabriel · trial leads
    "migration-checklist": "gabrielrm",   # Gabriel · seguimiento descargas
    "retail-guide":        "gabrielrm",
    "demo-request":        "gabrielrm",
    "consultation-request":"jeanlouis",
}

# Sales team al que se asignan TODOS los leads de marketing inbound.
# Si no existe se cae al primer team de la compañía.
INBOUND_TEAM_NAME = "Nextdoo"

# Stage destino para todo lead inbound recién capturado.
INBOUND_STAGE_NAME = "Lead Inbound"

# Tag automático de línea de negocio (se añade en todos los inbound).
INBOUND_LINEA_TAG = "Línea: Nextdoo"

# Sources que requieren generar y adjuntar un PDF al lead + email.
# El HTML del email lo genera _html_<source>() en Python (Odoo 19 no soporta
# {{ object.field }} en mail.template).
ATTACHMENT_BY_SOURCE = {
    "migration-checklist": {
        "report_xmlid": "nextdoo_lead_capture.action_report_checklist_migracion",
        "filename":     "Checklist_Migracion_Odoo_Nextdoo.pdf",
    },
    "retail-guide": {
        "report_xmlid": "nextdoo_lead_capture.action_report_retail_guide",
        "filename":     "Guia_Odoo_Retail_Nextdoo.pdf",
    },
}

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
            # 1. Resolve assignee por source · cada landing tiene su comercial.
            target_login = ASSIGNEE_BY_SOURCE.get(source, DEFAULT_ASSIGNEE_LOGIN)
            assignee = env["res.users"].search([("login", "=", target_login)], limit=1)
            if not assignee:
                # Fallback al default
                assignee = env["res.users"].search(
                    [("login", "=", DEFAULT_ASSIGNEE_LOGIN)], limit=1
                )
            if not assignee:
                assignee = env.ref("base.user_admin", raise_if_not_found=False)
            if not assignee:
                assignee = env["res.users"].search([("share", "=", False)], limit=1)

            # 2. Resolve/create tags (añadimos tag por tier + tag de línea)
            tag_names = list(SOURCE_TAGS.get(source, ["Lead Magnet"]))
            tag_names.append(INBOUND_LINEA_TAG)  # clasificación de línea de negocio
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

            # 3. Resolve sales team · inbound marketing va a "BOO NUEVO".
            team = env["crm.team"].search(
                [("name", "=ilike", INBOUND_TEAM_NAME)], limit=1
            )
            if not team:
                team = env["crm.team"].search(
                    [("company_id", "=", env.company.id)], limit=1
                )

            # 4. Priority — tier meeting siempre 3★ (lead caliente),
            #    tier email se rige por urgencia declarada (suele ser baja).
            if tier == "meeting":
                priority = "3" if timeline in ("3m", "6m") else "2"
            else:
                priority_map = {"3m": "2", "6m": "1", "12m": "1", "explorar": "0"}
                priority = priority_map.get(timeline, "1")

            # 5. Resolve stage · todo inbound aterriza en "Lead Inbound"
            #    (stage canónica del pipeline unificado).
            stage = env["crm.stage"].search(
                [("name", "=", INBOUND_STAGE_NAME)], limit=1,
            )
            if not stage:
                # Fallback: primera stage no plegada (Nuevo, Lead Inbound…)
                stage = env["crm.stage"].search(
                    [("fold", "=", False)],
                    order="sequence asc", limit=1,
                )

            # 6. Create OPPORTUNITY (no "lead" — aparece directo en Pipeline)
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
                "stage_id": stage.id if stage else False,
                "priority": priority,
                "type": "opportunity",
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

            # 8. Generar PDF si la source lo necesita (checklist…)
            attached_id = self._maybe_attach_resource(env, lead, source)

            # 9. Email interno al asignado (HTML pre-renderizado f-string)
            self._send_internal_notif(env, lead, source, tier, timeline, assignee, description)

            # 10. Email al cliente · con adjunto si aplica
            customer_sent = self._send_customer_email(
                env, lead, source, tier, attached_id
            )

            return _json_response(
                {
                    "ok": True,
                    "lead_id": lead.id,
                    "source": source,
                    "tier": tier,
                    "attachment_id": attached_id,
                    "email_sent": customer_sent,
                    "team_id": team.id if team else None,
                    "user_id": assignee.id if assignee else None,
                },
                200,
                origin,
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
    def _send_internal_notif(env, lead, source, tier, timeline, assignee, description):
        """Notifica al comercial asignado con HTML pre-renderizado."""
        if not assignee or not assignee.email:
            return
        is_hot = tier == "meeting"
        header_color = "#EF4444" if is_hot else "#6b7280"
        badge_label = "HOT LEAD · sesión 1-1" if is_hot else "COLD LEAD · solo email"
        action_label = (
            "Acción HOY: llamar inmediatamente, lead solicitó sesión 1-1."
            if is_hot else
            "Follow-up en 48 h: enviar PDF + ofrecer upgrade a sesión 1-1."
        )
        action_bg = "#fee2e2" if is_hot else "#fef3c7"
        action_color = "#991b1b" if is_hot else "#92400e"

        base_url = env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        body_html = f"""
<div style="font-family:'Inter',Arial,sans-serif;max-width:600px;margin:0 auto;background:#f7f7f8">
  <div style="background:linear-gradient(135deg,{header_color} 0%,#EC4899 100%);padding:24px;color:white">
    <div style="display:inline-block;background:rgba(255,255,255,0.2);padding:4px 10px;border-radius:99px;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px">{badge_label}</div>
    <h1 style="margin:0;font-size:22px;font-weight:800">Nuevo lead capturado</h1>
    <p style="margin:4px 0 0;opacity:0.9;font-size:14px">Fuente: <strong>{source}</strong> · Urgencia: <strong>{timeline}</strong></p>
  </div>
  <div style="padding:24px;background:white">
    <h2 style="margin:0 0 16px;color:#111;font-size:18px">{lead.partner_name or '—'}</h2>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <tr><td style="padding:8px 0;color:#6b7280">Contacto</td><td style="padding:8px 0"><strong>{lead.contact_name or '—'}</strong></td></tr>
      <tr><td style="padding:8px 0;color:#6b7280">Email</td><td style="padding:8px 0"><a href="mailto:{lead.email_from or ''}" style="color:#A855F7">{lead.email_from or '—'}</a></td></tr>
      <tr><td style="padding:8px 0;color:#6b7280">Teléfono</td><td style="padding:8px 0"><a href="tel:{lead.phone or ''}" style="color:#A855F7">{lead.phone or '—'}</a></td></tr>
      <tr><td style="padding:8px 0;color:#6b7280">Prioridad</td><td style="padding:8px 0">{lead.priority} ★</td></tr>
    </table>
    <div style="background:#f9fafb;border-left:4px solid #A855F7;padding:12px 16px;margin-top:16px;font-family:monospace;white-space:pre-wrap;font-size:12px;color:#374151">{description}</div>
    <div style="margin-top:24px;padding:16px;background:{action_bg};border-radius:8px;color:{action_color};font-size:14px"><strong>{action_label}</strong></div>
    <a href="{base_url}/odoo/action-crm.crm_lead_all_leads/{lead.id}" style="display:inline-block;background:linear-gradient(135deg,#A855F7,#EC4899);color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700;margin-top:16px;font-size:14px">Abrir lead en Odoo →</a>
  </div>
  <div style="padding:16px 24px;background:#111;color:#9ca3af;font-size:11px;text-align:center">Nextdoo Lead Magnet Engine · {lead.id}</div>
</div>
""".strip()

        # auto_delete=False para que quede traza en la queue si falla SMTP.
        mail = env["mail.mail"].create({
            "subject": f"[{tier.upper()}] {lead.partner_name} · {source}",
            "body_html": body_html,
            "email_from": "info@nextdoo.cloud",
            "email_to": assignee.email,
            "auto_delete": False,
        })
        try:
            mail.send(raise_exception=False)
        except Exception as e:
            _logger.warning("internal notif send failed: %s", e)

    @staticmethod
    def _send_customer_email(env, lead, source, tier, attached_id):
        """Envía email al lead. Si hay PDF asociado lo adjunta."""
        if not lead.email_from:
            return False

        attachment_ids = [(6, 0, [attached_id])] if attached_id else False

        if source == "migration-checklist":
            subject, body_html, from_addr = LeadMagnetController._html_checklist(lead)
        elif source == "retail-guide":
            subject, body_html, from_addr = LeadMagnetController._html_retail_guide(lead)
        elif source == "roi-calculator" and tier == "email":
            subject, body_html, from_addr = LeadMagnetController._html_roi_summary(lead)
        else:
            # No customer email para tier meeting (Jeanlouis llama directamente)
            return False

        try:
            mail_vals = {
                "subject": subject,
                "body_html": body_html,
                "email_from": from_addr,
                "email_to": lead.email_from,
                "reply_to": from_addr,
                "auto_delete": False,  # mantener traza si SMTP falla
            }
            if attachment_ids:
                mail_vals["attachment_ids"] = attachment_ids
            mail = env["mail.mail"].create(mail_vals)
            mail.send(raise_exception=False)
            return True
        except Exception as e:
            _logger.warning("customer email failed: %s", e)
            return False

    @staticmethod
    def _html_checklist(lead):
        base = lead.env["ir.config_parameter"].sudo().get_param("web.base.url", "https://www.nextdoo.cloud")
        contact = lead.contact_name or ""
        subject = "Aquí tienes tu Checklist Migración Odoo (42 puntos)"
        from_addr = '"Gabriel · Nextdoo" <gabrielrm@nextdoo.cloud>'
        body = f"""
<div style="font-family:'Inter',Arial,sans-serif;max-width:600px;margin:0 auto;background:#0A0A0A;color:#fff">
  <div style="background:linear-gradient(135deg,#A855F7 0%,#EC4899 100%);padding:28px 24px">
    <h1 style="margin:0;font-size:24px;font-weight:800;color:#fff">Tu checklist de migración a Odoo</h1>
    <p style="margin:6px 0 0;color:rgba(255,255,255,0.85);font-size:14px">42 puntos críticos · método Nextdoo · adjunto en PDF</p>
  </div>
  <div style="padding:28px 24px;background:#111114">
    <p style="font-size:16px;color:#fff;margin:0 0 16px">Hola {contact},</p>
    <p style="font-size:14px;color:rgba(255,255,255,0.78);line-height:1.65;margin:0 0 16px">
      Gracias por descargar nuestro <strong style="color:#fff">checklist de migración a Odoo</strong>.
      Es la guía paso a paso que usamos en cada implantación: las cuatro fases (discovery, configuración,
      migración de datos y go-live) con los 42 puntos críticos que evitan que algo falle al cambiar de sistema.
    </p>
    <p style="font-size:14px;color:rgba(255,255,255,0.78);line-height:1.65;margin:0 0 16px">
      <strong style="color:#fff">→ Lo tienes adjunto a este email en PDF.</strong>
    </p>
    <div style="background:rgba(168,85,247,0.10);border:1px solid rgba(168,85,247,0.3);border-radius:12px;padding:18px;margin:20px 0">
      <h3 style="margin:0 0 8px;font-size:15px;color:#fff">¿Te ayudo a aplicarlo a tu caso?</h3>
      <p style="font-size:13px;color:rgba(255,255,255,0.78);margin:0 0 12px;line-height:1.6">
        Soy Gabriel, parte del equipo Nextdoo. Si quieres, en 20 minutos revisamos contigo
        qué puntos del checklist son críticos para tu sector y tamaño. Sin compromiso, sin presión.
      </p>
      <a href="https://www.nextdoo.cloud/appointment" style="display:inline-block;background:linear-gradient(135deg,#A855F7,#EC4899);color:#fff;padding:11px 22px;border-radius:8px;text-decoration:none;font-weight:700;font-size:13px">Reservar 20 min con Gabriel →</a>
    </div>
    <p style="font-size:13px;color:rgba(255,255,255,0.65);line-height:1.6;margin:24px 0 0">
      Y si prefieres responder por email contándome tu situación
      (sistema actual, tamaño y plazo), te preparo un plan personalizado.
    </p>
    <p style="font-size:13px;color:rgba(255,255,255,0.65);margin:8px 0 0">
      Un saludo,<br/>
      <strong style="color:#fff">Gabriel Rodes Maganto</strong><br/>
      Comercial · Nextdoo Cloud<br/>
      <a href="tel:+34622891192" style="color:#A855F7">+34 622 891 192</a> · <a href="mailto:gabrielrm@nextdoo.cloud" style="color:#A855F7">gabrielrm@nextdoo.cloud</a>
    </p>
  </div>
  <div style="padding:16px 24px;background:#0A0A0A;color:#6b7280;font-size:11px;text-align:center">
    Nextdoo Cloud · Odoo Ready Partner · Valencia, España ·
    <a href="https://www.nextdoo.cloud/politica-privacidad" style="color:#6b7280">Política de privacidad</a>
  </div>
</div>
""".strip()
        return subject, body, from_addr

    @staticmethod
    def _html_retail_guide(lead):
        contact = lead.contact_name or ""
        subject = "Tu Guía Odoo Retail · 36 decisiones clave"
        from_addr = '"Gabriel · Nextdoo" <gabrielrm@nextdoo.cloud>'
        body = f"""
<div style="font-family:'Inter',Arial,sans-serif;max-width:600px;margin:0 auto;background:#0A0A0A;color:#fff">
  <div style="background:linear-gradient(135deg,#A855F7 0%,#EC4899 100%);padding:28px 24px">
    <h1 style="margin:0;font-size:24px;font-weight:800;color:#fff">Tu Guía Odoo Retail</h1>
    <p style="margin:6px 0 0;color:rgba(255,255,255,0.85);font-size:14px">36 decisiones clave para retail España · adjunto en PDF</p>
  </div>
  <div style="padding:28px 24px;background:#111114">
    <p style="font-size:16px;color:#fff;margin:0 0 16px">Hola {contact},</p>
    <p style="font-size:14px;color:rgba(255,255,255,0.78);line-height:1.65;margin:0 0 16px">
      Aquí tienes la guía completa de <strong style="color:#fff">implantación Odoo para retail</strong>:
      TPV, inventario multi-tienda, e-commerce sincronizado, contabilidad VeriFactu lista para 2026,
      fidelización y reporting. Las 36 decisiones que aplicamos en cada proyecto, organizadas en 6 áreas.
    </p>
    <p style="font-size:14px;color:rgba(255,255,255,0.78);line-height:1.65;margin:0 0 16px">
      <strong style="color:#fff">→ Adjunta a este email en PDF (~5 páginas).</strong>
    </p>
    <div style="background:rgba(168,85,247,0.10);border:1px solid rgba(168,85,247,0.3);border-radius:12px;padding:18px;margin:20px 0">
      <h3 style="margin:0 0 8px;font-size:15px;color:#fff">¿La aplicamos a tu retail?</h3>
      <p style="font-size:13px;color:rgba(255,255,255,0.78);margin:0 0 12px;line-height:1.6">
        Soy Gabriel del equipo Nextdoo. Si quieres, en 20 minutos revisamos juntos qué decisiones
        de la guía son críticas para tu negocio (moda, deportes, hogar, alimentación, electrónica…),
        tu volumen y tu plazo. Sin compromiso.
      </p>
      <a href="https://www.nextdoo.cloud/appointment/2" style="display:inline-block;background:linear-gradient(135deg,#A855F7,#EC4899);color:#fff;padding:11px 22px;border-radius:8px;text-decoration:none;font-weight:700;font-size:13px">Reservar 20 min con Gabriel →</a>
    </div>
    <p style="font-size:13px;color:rgba(255,255,255,0.65);line-height:1.6;margin:24px 0 0">
      Si prefieres respondemos por email — cuéntame tu situación (cuántas tiendas, sistema actual,
      objetivo) y te preparo recomendación personalizada.
    </p>
    <p style="font-size:13px;color:rgba(255,255,255,0.65);margin:8px 0 0">
      Un saludo,<br/>
      <strong style="color:#fff">Gabriel Rodes Maganto</strong><br/>
      Comercial · Nextdoo Cloud · Partner Odoo Retail España<br/>
      <a href="tel:+34622891192" style="color:#A855F7">+34 622 891 192</a> · <a href="mailto:gabrielrm@nextdoo.cloud" style="color:#A855F7">gabrielrm@nextdoo.cloud</a>
    </p>
  </div>
  <div style="padding:16px 24px;background:#0A0A0A;color:#6b7280;font-size:11px;text-align:center">
    Nextdoo Cloud · Odoo Ready Partner · Valencia, España ·
    <a href="https://www.nextdoo.cloud/politica-privacidad" style="color:#6b7280">Política de privacidad</a>
  </div>
</div>
""".strip()
        return subject, body, from_addr

    @staticmethod
    def _html_roi_summary(lead):
        base = lead.env["ir.config_parameter"].sudo().get_param("web.base.url", "https://www.nextdoo.cloud")
        contact = lead.contact_name or ""
        subject = "Tu análisis ROI Odoo — Nextdoo"
        from_addr = '"Jeanlouis · Nextdoo" <jeanlouis@nextdoo.cloud>'
        body = f"""
<div style="font-family:'Inter',Arial,sans-serif;max-width:600px;margin:0 auto;background:#0A0A0A;color:#fff">
  <div style="background:linear-gradient(135deg,#A855F7 0%,#EC4899 100%);padding:28px 24px">
    <h1 style="margin:0;font-size:24px;font-weight:800;color:#fff">Tu análisis ROI Odoo</h1>
    <p style="margin:6px 0 0;color:rgba(255,255,255,0.85);font-size:14px">Resumen automático · Nextdoo Cloud · Partner Odoo Retail España</p>
  </div>
  <div style="padding:28px 24px;background:#111114">
    <p style="font-size:16px;color:#fff;margin:0 0 16px">Hola {contact},</p>
    <p style="font-size:14px;color:rgba(255,255,255,0.78);line-height:1.65;margin:0 0 20px">
      Gracias por usar nuestra calculadora ROI. Aquí tienes el resumen automático con tus números.
    </p>
    <div style="background:linear-gradient(180deg,rgba(168,85,247,0.10),rgba(236,72,153,0.05));border:1px solid rgba(168,85,247,0.45);border-radius:12px;padding:24px;margin:20px 0;text-align:center">
      <p style="margin:0 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;color:rgba(255,255,255,0.6);font-weight:600">Próximo paso recomendado</p>
      <h3 style="margin:0 0 8px;color:#fff;font-size:20px">Sesión 1-1 gratuita con Jeanlouis (CEO)</h3>
      <p style="margin:0 0 16px;color:rgba(255,255,255,0.78);font-size:14px;line-height:1.6">
        Validamos tus cifras con tu equipo, entregamos plan de implementación a 90 días<br/>y revisamos qué módulos son críticos para tu sector. Sin compromiso.
      </p>
      <a href="https://www.nextdoo.cloud/appointment" style="display:inline-block;background:linear-gradient(135deg,#A855F7,#EC4899);color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700;font-size:14px">Reservar 30 min con Jeanlouis →</a>
    </div>
    <p style="font-size:13px;color:rgba(255,255,255,0.65);margin:24px 0 0">
      Un saludo,<br/>
      <strong style="color:#fff">Jeanlouis Rodes</strong><br/>
      CEO · Nextdoo Cloud<br/>
      <a href="tel:+34622891192" style="color:#A855F7">+34 622 891 192</a>
    </p>
  </div>
  <div style="padding:16px 24px;background:#0A0A0A;color:#6b7280;font-size:11px;text-align:center">
    Nextdoo Cloud · Odoo Ready Partner · Valencia, España
  </div>
</div>
""".strip()
        return subject, body, from_addr

    @staticmethod
    def _maybe_attach_resource(env, lead, source):
        """Si la source tiene un PDF asociado, lo genera y adjunta al lead.

        Genera el report QWeb-PDF, crea un ir.attachment vinculado al lead,
        y opcionalmente guarda copia en documents.document si el módulo
        está instalado. Devuelve el id del attachment o None.
        """
        cfg = ATTACHMENT_BY_SOURCE.get(source)
        if not cfg:
            return None
        try:
            report = env.ref(cfg["report_xmlid"], raise_if_not_found=False)
            if not report:
                _logger.warning("attach: report %s not found", cfg["report_xmlid"])
                return None

            pdf_data, _content_type = report._render_qweb_pdf(
                cfg["report_xmlid"], res_ids=[lead.id]
            )
            attachment = env["ir.attachment"].create({
                "name": cfg["filename"],
                "type": "binary",
                "raw": pdf_data,
                "mimetype": "application/pdf",
                "res_model": "crm.lead",
                "res_id": lead.id,
            })

            # Si documents está instalado, guardar copia (catálogo central)
            if "documents.document" in env:
                try:
                    folder = env["documents.folder"].search(
                        [("name", "=ilike", "Lead Magnets")], limit=1
                    )
                    if not folder:
                        folder = env["documents.folder"].create({"name": "Lead Magnets"})
                    env["documents.document"].create({
                        "name": cfg["filename"],
                        "datas": attachment.datas,
                        "folder_id": folder.id,
                        "mimetype": "application/pdf",
                        "owner_id": lead.user_id.id if lead.user_id else env.user.id,
                    })
                except Exception as e:
                    _logger.warning("attach: documents.document save failed: %s", e)

            return attachment.id
        except Exception as e:
            _logger.exception("attach: pdf generation failed for source=%s", source)
            return None

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
