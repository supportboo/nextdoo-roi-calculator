"""
migrate_crm_pipeline.py · Unifica el CRM de Nextdoo a 7 stages canónicas.

PRESERVA SIEMPRE:
- Leads en stages BOO (29, 30, 31, 32, 33)
- Leads en teams Boo (8) y BOO NUEVO (9)
- Tags existentes en cada lead (solo SE AÑADE el tag de línea)

CREA:
- 7 stages: Lead Inbound · Nuevo · Calificado · Demo · Presupuestado · Negociado · Ganado
- 4 tags de línea: Nextdoo, Folder, Modeka, Motodoo

RENOMBRA:
- Team "Sales" → "Nextdoo"
"""

import argparse, os, sys, xmlrpc.client

URL = 'https://www.nextdoo.cloud'
DB = 'nextdoo-sh-nextdoo-main-27318398'
USER = 'jeanlouis'

# Stages canónicas finales (orden = sequence)
CANONICAL_STAGES = [
    ('Lead Inbound',  1, False),
    ('Nuevo',         2, False),
    ('Calificado',    3, False),
    ('Demo',          4, False),
    ('Presupuestado', 5, False),
    ('Negociado',     6, False),
    ('Ganado',        7, True),   # is_won
]

# Mapeo old stage_id → nombre de la stage nueva
STAGE_MAP = {
    # Lead inbound (entrada cruda)
    21: 'Lead Inbound',   # INICIATIVA — 211
    6:  'Lead Inbound',   # Iniciativa (fold) — 29
    # Nuevo
    1:  'Nuevo',          # Nuevo — 359
    13: 'Nuevo',          # Nuevo (duplicado) — 51
    8:  'Nuevo',          # NUEVOS PEDIDOS — 20
    14: 'Nuevo',          # Contactado — 12
    24: 'Nuevo',          # FOLDER CONTACTADO — 0
    # Calificado
    9:  'Calificado',     # LEADS CUALIFICADOS — 12
    27: 'Calificado',     # NEXTDOO SPONSOR — 9
    # Presupuestado
    11: 'Presupuestado',  # MODEKA PROFORMAS — 3
    10: 'Presupuestado',  # PROPUESTA ENVIADA — 1
    25: 'Presupuestado',  # FOLDER PROPUESTA — 0
    # Negociado
    7:  'Negociado',      # Negociación — 13
    28: 'Negociado',      # NEXTDOO NEGOCIACION — 6
    # Ganado
    4:  'Ganado',         # Ganado — 68 (is_won)
    18: 'Ganado',         # Ganado — 1 (is_won)
    23: 'Ganado',         # GANADO — 21 (is_won)
    26: 'Ganado',         # FOLDER GANADO — 0 (is_won)
}

# Stages que NO se tocan (líneas BOO)
STAGES_KEEP = {29, 30, 31, 32, 33}

# Teams a no tocar (BOO/Boomatik)
TEAMS_KEEP = {8, 9}

# Team → tag de línea de negocio
TEAM_TO_LINEA = {
    1: 'Línea: Nextdoo',   # Sales (luego Nextdoo)
    6: 'Línea: Folder',    # Folder Manager
    4: 'Línea: Modeka',
    5: 'Línea: Motodoo',
}
DEFAULT_LINEA = 'Línea: Nextdoo'   # leads sin team van a Nextdoo
DEFAULT_TEAM_NAME = 'Nextdoo'      # team destino para huérfanos

# Tags a crear
LINEA_TAGS = {
    'Línea: Nextdoo': 11,   # color verde-azulado
    'Línea: Folder':   3,   # color amarillo
    'Línea: Modeka':   8,   # color azul claro
    'Línea: Motodoo':  6,   # color naranja
}


def connect():
    api_key = os.environ.get('NEXTDOO_API_KEY')
    if not api_key:
        sys.exit('Falta NEXTDOO_API_KEY')
    uid = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common').authenticate(DB, USER, api_key, {})
    if not uid:
        sys.exit('Auth fallido')
    m = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
    return uid, m, api_key


def upsert_stage(m, uid, K, name, sequence, is_won):
    existing = m.execute_kw(DB, uid, K, 'crm.stage', 'search',
                            [[('name', '=', name)]], {'limit': 1})
    if existing:
        m.execute_kw(DB, uid, K, 'crm.stage', 'write',
                     [existing, {'sequence': sequence, 'is_won': is_won, 'fold': False}])
        return existing[0], False
    vals = {'name': name, 'sequence': sequence, 'is_won': is_won, 'fold': False}
    return m.execute_kw(DB, uid, K, 'crm.stage', 'create', [vals]), True


def upsert_tag(m, uid, K, name, color):
    existing = m.execute_kw(DB, uid, K, 'crm.tag', 'search',
                            [[('name', '=', name)]], {'limit': 1})
    if existing:
        return existing[0], False
    return m.execute_kw(DB, uid, K, 'crm.tag', 'create',
                        [{'name': name, 'color': color}]), True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='solo muestra qué cambiaría')
    args = parser.parse_args()

    uid, m, K = connect()
    print(f'Conectado uid={uid}')
    if args.dry_run:
        print('=== DRY-RUN · no escribe nada ===\n')
    else:
        print('=== APLICANDO CAMBIOS REALES ===\n')

    # === FASE 1 · Crear stages canónicas ===
    print('FASE 1 · Stages canónicas')
    stage_name_to_id = {}
    for name, seq, is_won in CANONICAL_STAGES:
        if args.dry_run:
            existing = m.execute_kw(DB, uid, K, 'crm.stage', 'search',
                                    [[('name', '=', name)]], {'limit': 1})
            print(f'  {"existe" if existing else "crear":<7} · seq={seq} won={is_won} · {name}')
            stage_name_to_id[name] = existing[0] if existing else None
        else:
            sid, created = upsert_stage(m, uid, K, name, seq, is_won)
            stage_name_to_id[name] = sid
            print(f'  id={sid:<3} {"creada" if created else "ok":<7} · seq={seq} won={is_won} · {name}')

    # === FASE 2 · Crear tags de línea ===
    print('\nFASE 2 · Tags de línea')
    tag_name_to_id = {}
    for tname, color in LINEA_TAGS.items():
        if args.dry_run:
            existing = m.execute_kw(DB, uid, K, 'crm.tag', 'search',
                                    [[('name', '=', tname)]], {'limit': 1})
            tag_name_to_id[tname] = existing[0] if existing else None
            print(f'  {"existe" if existing else "crear":<7} · {tname}')
        else:
            tid, created = upsert_tag(m, uid, K, tname, color)
            tag_name_to_id[tname] = tid
            print(f'  id={tid:<4} {"creada" if created else "ok":<7} · {tname}')

    # === FASE 3 · Renombrar team Sales → Nextdoo ===
    print('\nFASE 3 · Rename team Sales → Nextdoo')
    sales = m.execute_kw(DB, uid, K, 'crm.team', 'search',
                         [[('name', '=', 'Sales')]], {'limit': 1})
    if sales:
        if args.dry_run:
            print(f'  team id={sales[0]} → renombrar Sales → {DEFAULT_TEAM_NAME}')
        else:
            m.execute_kw(DB, uid, K, 'crm.team', 'write', [sales, {'name': DEFAULT_TEAM_NAME}])
            print(f'  team id={sales[0]} renombrado a {DEFAULT_TEAM_NAME}')

    # === FASE 4 · Migración leads ===
    print('\nFASE 4 · Migración de leads')

    # Build domain: leads cuyo stage está en STAGE_MAP y team_id NOT IN TEAMS_KEEP
    candidate_ids = m.execute_kw(DB, uid, K, 'crm.lead', 'search', [[
        ('active', 'in', [True, False]),
        ('stage_id', 'in', list(STAGE_MAP.keys())),
        '|', ('team_id', 'not in', list(TEAMS_KEEP)), ('team_id', '=', False),
    ]])
    print(f'  Candidatos a migrar: {len(candidate_ids)}')

    # Process por chunks
    by_target = {}   # stage_name -> count
    by_linea = {}    # tag_name -> count
    no_team_count = 0
    untouched = 0

    nextdoo_team_id = sales[0] if sales else None

    for i in range(0, len(candidate_ids), 100):
        batch_ids = candidate_ids[i:i+100]
        leads = m.execute_kw(DB, uid, K, 'crm.lead', 'read', [batch_ids],
                             {'fields': ['id', 'stage_id', 'team_id', 'tag_ids']})
        for lead in leads:
            old_stage = lead['stage_id'][0] if lead['stage_id'] else None
            team_id = lead['team_id'][0] if lead['team_id'] else None

            # Determinar stage nueva
            target_stage_name = STAGE_MAP.get(old_stage)
            if not target_stage_name:
                untouched += 1
                continue

            # Determinar tag línea
            linea_tag = TEAM_TO_LINEA.get(team_id, DEFAULT_LINEA)

            # Determinar team destino (huérfanos → Nextdoo)
            new_team_id = team_id if team_id else nextdoo_team_id
            if not team_id:
                no_team_count += 1

            # Update vals
            vals = {'stage_id': stage_name_to_id[target_stage_name]}
            if new_team_id and not team_id:
                vals['team_id'] = new_team_id
            # Tag: usar comando (4, id) que añade sin tocar resto
            if linea_tag in tag_name_to_id and tag_name_to_id[linea_tag]:
                vals['tag_ids'] = [(4, tag_name_to_id[linea_tag])]

            if not args.dry_run:
                m.execute_kw(DB, uid, K, 'crm.lead', 'write', [[lead['id']], vals])

            by_target[target_stage_name] = by_target.get(target_stage_name, 0) + 1
            by_linea[linea_tag] = by_linea.get(linea_tag, 0) + 1

        if not args.dry_run:
            print(f'  procesados {min(i+100, len(candidate_ids))}/{len(candidate_ids)}')

    print('\n--- Resumen migración ---')
    print('Por stage destino:')
    for name in [s[0] for s in CANONICAL_STAGES]:
        print(f'  {name:<14}: {by_target.get(name, 0)}')
    print(f'  (no mapeable):  {untouched}')
    print('Por línea (tag):')
    for tname in LINEA_TAGS:
        print(f'  {tname:<20}: {by_linea.get(tname, 0)}')
    print(f'Leads sin team reasignados a Nextdoo: {no_team_count}')

    # === FASE 5 · Archivar stages viejas (no BOO) ===
    print('\nFASE 5 · Archivar stages viejas (no-BOO)')
    canonical_ids = {sid for sid in stage_name_to_id.values() if sid}
    old_to_archive = []
    for old_id in STAGE_MAP.keys():
        if old_id in canonical_ids or old_id in STAGES_KEEP:
            continue
        old_to_archive.append(old_id)
    print(f'  Stages a archivar: {old_to_archive}')
    if old_to_archive and not args.dry_run:
        m.execute_kw(DB, uid, K, 'crm.stage', 'write', [old_to_archive, {'active': False}])
        print(f'  ✓ Archivadas {len(old_to_archive)} stages')

    # === FASE 6 · Verificación ===
    print('\nFASE 6 · Verificación post-migración')
    for name in [s[0] for s in CANONICAL_STAGES]:
        sid = stage_name_to_id[name]
        if sid:
            c = m.execute_kw(DB, uid, K, 'crm.lead', 'search_count',
                             [[('stage_id', '=', sid), ('active', 'in', [True, False])]])
            print(f'  {name:<14} (id {sid}): {c} leads')
    # BOO stages intactas
    print('  --- BOO (intactos) ---')
    for boo_id in sorted(STAGES_KEEP):
        s = m.execute_kw(DB, uid, K, 'crm.stage', 'read', [[boo_id]], {'fields': ['name']})
        if s:
            c = m.execute_kw(DB, uid, K, 'crm.lead', 'search_count',
                             [[('stage_id', '=', boo_id), ('active', 'in', [True, False])]])
            print(f'  {s[0]["name"]:<20} (id {boo_id}): {c} leads')


if __name__ == '__main__':
    main()
