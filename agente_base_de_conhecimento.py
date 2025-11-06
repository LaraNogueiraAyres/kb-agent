#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
kb_agent_menu.py — Ferramenta genérica para SBC com menu, import .txt e catálogo de variáveis.

Recursos:
- Editor de Base de Conhecimento (regras SE...ENTÃO..., fatos c/ picker de variável)
- Motor de Inferência (Forward e Backward)
- Explanação (Por quê? Como?)
- Menu numérico + aliases + correspondência parcial
- Importação de regras via .txt (uma por linha; # e // como comentários)
- Catálogo automático de variáveis derivadas das regras (evita typos)
- Undo 1 passo para operações mutáveis

Novidades:
- Picker de **objetivo** no comando "provar": escolhe variável-alvo (de conclusões) e valor sugerido pelas regras.
- Picker de **fato** usa só variáveis de **condição** e mostra exemplos de valores (das condições).
"""

import json
import re
import os
import difflib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union, Set

# ========= Representações básicas =========

Condition = Dict[str, Any]   # {"attr": "Temperatura", "op": ">", "value": 38.7}
Conclusion = Dict[str, Any]  # {"attr": "Risk_Level", "op": "=", "value": "High"}

@dataclass
class Rule:
    id: int
    conditions: List[Condition]
    conclusion: Conclusion
    text: str = ""  # texto original da regra para explanação

@dataclass
class Fact:
    attr: str
    value: Any

@dataclass
class Justification:
    fact: Fact
    rule_id: Optional[int] = None
    premises: List[Fact] = field(default_factory=list)
    note: str = ""  # "base" | "forward (it=k)" | "backward"

class KnowledgeBase:
    def __init__(self):
        self.facts: Dict[str, Any] = {}             # attr -> valor (último)
        self.rules: List[Rule] = []
        self.justifications: Dict[str, Justification] = {}  # attr -> justificativa
        self._next_rule_id = 1

        # Catálogos
        self.attributes: Set[str] = set()                 # todos os attrs (condições + conclusões)
        self._cond_attrs: Set[str] = set()                # só attrs que aparecem em condições (SE ...)
        self._concl_attrs: Set[str] = set()               # só attrs que aparecem em conclusões (ENTÃO ...)

    # ----- Variáveis (catálogo) -----
    def _touch_attribute(self, attr: Optional[str], where: str = "any"):
        if isinstance(attr, str) and attr.strip():
            a = attr.strip()
            self.attributes.add(a)
            if where == "cond":
                self._cond_attrs.add(a)
            elif where == "concl":
                self._concl_attrs.add(a)

    def _extract_attributes_from_rule(self, r: Rule):
        for c in r.conditions:
            self._touch_attribute(c.get("attr"), where="cond")
        self._touch_attribute(r.conclusion.get("attr"), where="concl")

    def _rebuild_attributes(self):
        self.attributes = set()
        self._cond_attrs = set()
        self._concl_attrs = set()
        for r in self.rules:
            self._extract_attributes_from_rule(r)

    def get_attributes(self) -> List[str]:
        return sorted(self.attributes)

    def get_attributes_for_facts(self) -> List[str]:
        return sorted(self._cond_attrs)

    def get_conclusion_attributes(self) -> List[str]:
        return sorted(self._concl_attrs)

    # Exemplos de valores (das CONDIÇÕES)
    def get_example_values_for_attr(self, attr: str, max_n: int = 5) -> List[Any]:
        seen = []
        for r in self.rules:
            for c in r.conditions:
                if c.get("attr") == attr:
                    v = c.get("value")
                    if v not in seen:
                        seen.append(v)
                        if len(seen) >= max_n:
                            return seen
        return seen

    # Valores candidatos (das CONCLUSÕES) para um objetivo
    def get_goal_values_for_attr(self, attr: str, max_n: Optional[int] = None) -> List[Any]:
        seen = []
        for r in self.rules:
            concl = r.conclusion
            if concl.get("attr") == attr:
                v = concl.get("value")
                if v not in seen:
                    seen.append(v)
                    if max_n and len(seen) >= max_n:
                        return seen
        return seen

    # ----- Fatos -----
    def add_fact(self, attr: str, value: Any, note: str = "base"):
        self.facts[attr] = value
        self.justifications[attr] = Justification(Fact(attr, value), None, [], note)

    def has_fact(self, attr: str, value: Any = None) -> bool:
        if attr not in self.facts:
            return False
        return True if value is None else self.facts[attr] == value

    def get_fact(self, attr: str) -> Optional[Any]:
        return self.facts.get(attr)

    def list_facts(self) -> List[Fact]:
        return [Fact(k, v) for k, v in self.facts.items()]

    # ----- Regras -----
    def add_rule(self, conditions: List[Condition], conclusion: Conclusion, text: str = "") -> int:
        rid = self._next_rule_id
        self._next_rule_id += 1
        r = Rule(rid, conditions, conclusion, text)
        self.rules.append(r)
        self._extract_attributes_from_rule(r)
        return rid

    def list_rules(self) -> List[Rule]:
        return self.rules[:]

    def remove_rule(self, rid: int) -> bool:
        n = len(self.rules)
        self.rules = [r for r in self.rules if r.id != rid]
        if len(self.rules) < n:
            self._rebuild_attributes()
            return True
        return False

    # ----- Persistência -----
    def to_json(self) -> Dict[str, Any]:
        return {
            "facts": [{"attr": f.attr, "value": f.value} for f in self.list_facts()],
            "rules": [{
                "id": r.id,
                "conditions": r.conditions,
                "conclusion": r.conclusion,
                "text": r.text
            } for r in self.rules]
        }

    def load_json(self, obj: Dict[str, Any]):
        self.__init__()
        for f in obj.get("facts", []):
            self.add_fact(f["attr"], f["value"])
        for r in obj.get("rules", []):
            self._next_rule_id = max(self._next_rule_id, r.get("id", 0) + 1)
            rule = Rule(
                id=r["id"],
                conditions=r["conditions"],
                conclusion=r["conclusion"],
                text=r.get("text", "")
            )
            self.rules.append(rule)
        self._rebuild_attributes()

# ========= Avaliação de condições =========

def _cmp(a: Any, op: str, b: Any) -> bool:
    try:
        if op in ["=", "==", "é", "eh", "É"]:
            return a == b
        if op in ["!=", "≠"]:
            return a != b
        if op in ["<", "≤", "<="]:
            return float(a) <= float(b) if op in ("≤", "<=") else float(a) < float(b)
        if op in [">", "≥", ">="]:
            return float(a) >= float(b) if op in ("≥", ">=") else float(a) > float(b)
        if op.upper() == "IN":
            if isinstance(b, (list, tuple, set)):
                return a in b
            if isinstance(b, str) and b.strip().startswith("["):
                try:
                    lista = json.loads(b)
                    return a in lista
                except Exception:
                    return False
        return False
    except Exception:
        return False

def conditions_hold(kb: KnowledgeBase, conds: List[Condition]) -> Tuple[bool, List[Fact]]:
    used = []
    for c in conds:
        attr, op, val = c["attr"], c["op"], c["value"]
        if attr not in kb.facts:
            return False, []
        if not _cmp(kb.facts[attr], op, val):
            return False, []
        used.append(Fact(attr, kb.facts[attr]))
    return True, used

# ========= Forward chaining =========

def forward_chain(kb: KnowledgeBase, max_iterations: int = 50) -> List[Fact]:
    new_any = True
    inferred: List[Fact] = []
    it = 0
    while new_any and it < max_iterations:
        it += 1
        new_any = False
        for r in kb.rules:
            ok, used = conditions_hold(kb, r.conditions)
            if not ok:
                continue
            concl = r.conclusion
            attr, val = concl["attr"], concl["value"]
            if kb.has_fact(attr, val):
                continue
            kb.facts[attr] = val
            kb.justifications[attr] = Justification(
                Fact(attr, val), rule_id=r.id, premises=used, note=f"forward (it={it})"
            )
            inferred.append(Fact(attr, val))
            new_any = True
    return inferred

# ========= Backward chaining =========

def backward_prove(kb: KnowledgeBase, goal_attr: str, goal_val: Any,
                   visited: Set[Tuple[str, Any]] = None) -> bool:
    if visited is None:
        visited = set()
    if (goal_attr, goal_val) in visited:
        return False
    visited.add((goal_attr, goal_val))

    if kb.has_fact(goal_attr, goal_val):
        return True

    candidates = [r for r in kb.rules
                  if r.conclusion["attr"] == goal_attr and r.conclusion["value"] == goal_val]

    for r in candidates:
        premises_ok = True
        used_facts: List[Fact] = []
        for c in r.conditions:
            a, op, v = c["attr"], c["op"], c["value"]
            if a in kb.facts:
                if not _cmp(kb.facts[a], op, v):
                    premises_ok = False
                    break
                used_facts.append(Fact(a, kb.facts[a]))
            else:
                if op in ["=", "==", "é", "eh", "É"]:
                    if backward_prove(kb, a, v, visited):
                        used_facts.append(Fact(a, kb.facts.get(a, v)))
                    else:
                        premises_ok = False
                        break
                else:
                    premises_ok = False
                    break
        if premises_ok:
            kb.facts[goal_attr] = goal_val
            kb.justifications[goal_attr] = Justification(
                Fact(goal_attr, goal_val), rule_id=r.id, premises=used_facts, note="backward"
            )
            return True
    return False

# ========= Explanação =========

def explain_why(kb: KnowledgeBase, attr: str, val: Any, depth: int = 0) -> str:
    pad = "  " * depth
    if not kb.has_fact(attr, val):
        return f"{pad}- Não há fato {attr} = {val} na KB.\n"
    j = kb.justifications.get(attr)
    if not j:
        return f"{pad}- {attr} = {val} (sem justificativa registrada)\n"
    if j.rule_id is None:
        return f"{pad}- {attr} = {val} (fornecido pelo usuário / {j.note})\n"

    s = f"{pad}- {attr} = {val} porque aplicou a Regra #{j.rule_id}"
    r = next((rr for rr in kb.rules if rr.id == j.rule_id), None)
    if r and r.text:
        s += f" — '{r.text}'"
    s += f" [{j.note}]\n"
    for p in j.premises:
        jp = kb.justifications.get(p.attr)
        if jp and jp.rule_id is not None:
            s += explain_how(kb, p.attr, kb.facts[p.attr], depth + 1)
        else:
            s += f"{'  '*(depth+1)}- premissa: {p.attr} = {p.value} (conhecido)\n"
    return s

def explain_how(kb: KnowledgeBase, attr: str, val: Any, depth: int = 0) -> str:
    pad = "  " * depth
    if not kb.has_fact(attr, val):
        return f"{pad}- Não foi provado {attr} = {val}.\n"
    j = kb.justifications.get(attr)
    if not j or j.rule_id is None:
        return f"{pad}- {attr} = {val} (base / {j.note if j else 'sem nota'})\n"
    r = next((rr for rr in kb.rules if rr.id == j.rule_id), None)
    s = f"{pad}- Passo: {attr} = {val} via Regra #{j.rule_id}"
    if r and r.text:
        s += f" — '{r.text}'"
    s += f" [{j.note}]\n"
    for p in j.premises:
        s += explain_how(kb, p.attr, kb.facts.get(p.attr, p.value), depth + 1)
    return s

# ========= Parser PT-BR =========

_COND_RE = re.compile(
    r"^\s*([A-Za-z_À-ÿ0-9_]+)\s*(==|=|!=|≤|>=|<|>|≥|<=|>=|é|eh|É|IN)\s*(.+?)\s*$",
    re.IGNORECASE
)

def parse_value(raw: str) -> Any:
    raw = raw.strip()
    try:
        if "." in raw or raw.isdigit():
            return float(raw) if "." in raw else int(raw)
    except Exception:
        pass
    if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        try:
            return json.loads(raw)
        except Exception:
            return raw
    return raw

def parse_rule_pt(texto: str) -> Tuple[List[Condition], Conclusion]:
    t = texto.strip()
    t = t.replace("ENTAO", "ENTÃO").replace("->", "ENTÃO").replace("=>", "ENTÃO")
    m = re.split(r"\bENTÃO\b", t, flags=re.IGNORECASE)
    if len(m) != 2:
        raise ValueError("Regra deve conter 'SE ... ENTÃO ...'")
    lhs, rhs = m[0], m[1]
    if not lhs.strip().upper().startswith("SE"):
        raise ValueError("Parte esquerda deve iniciar com 'SE'")
    lhs = lhs.strip()[2:]
    parts = re.split(r"\bE\b", lhs, flags=re.IGNORECASE)
    conds: List[Condition] = []
    for p in parts:
        c = _COND_RE.match(p)
        if not c:
            raise ValueError(f"Não entendi condição: {p.strip()!r}")
        attr, op, valraw = c.group(1).strip(), c.group(2).strip(), c.group(3).strip()
        val = parse_value(valraw)
        if op == "==": op = "="
        conds.append({"attr": attr, "op": op, "value": val})

    c = _COND_RE.match(rhs)
    if not c:
        raise ValueError("Conclusão deve ser do tipo 'Attr = Valor'")
    concl_attr, concl_op, concl_valraw = c.group(1).strip(), c.group(2).strip(), c.group(3).strip()
    if concl_op not in ["=", "==", "é", "eh", "É"]:
        raise ValueError("Conclusão deve usar '=' (igualdade).")
    concl_val = parse_value(concl_valraw)
    conclusion = {"attr": concl_attr, "op": "=", "value": concl_val}
    return conds, conclusion

_FACT_RE = re.compile(r"^\s*([A-Za-z_À-ÿ0-9]+)\s*(==|=|é|eh|É)\s*(.+)\s*$", re.IGNORECASE)

def parse_fact_pt(texto: str) -> Fact:
    m = _FACT_RE.match(texto.strip())
    if not m:
        raise ValueError("Fato deve ser do tipo 'Attr = Valor'")
    attr, _, valraw = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    val = parse_value(valraw)
    return Fact(attr, val)

# ========= Undo (1 passo) =========

@dataclass
class Snapshot:
    facts: Dict[str, Any]
    justifications: Dict[str, Justification]
    rules: List[Rule]
    next_rule_id: int
    attributes: Set[str]
    cond_attrs: Set[str]
    concl_attrs: Set[str]

def snapshot_kb(kb: KnowledgeBase) -> Snapshot:
    jcopy = {k: Justification(Fact(v.fact.attr, v.fact.value), v.rule_id,
                              [Fact(p.attr, p.value) for p in v.premises], v.note)
             for k, v in kb.justifications.items()}
    rc = [Rule(r.id, list(r.conditions), dict(r.conclusion), r.text) for r in kb.rules]
    return Snapshot(
        dict(kb.facts),
        jcopy,
        rc,
        kb._next_rule_id,
        set(kb.attributes),
        set(kb._cond_attrs),
        set(kb._concl_attrs),
    )

def restore_kb(kb: KnowledgeBase, snap: Snapshot):
    kb.facts = dict(snap.facts)
    kb.justifications = {k: v for k, v in snap.justifications.items()}
    kb.rules = [Rule(r.id, r.conditions, r.conclusion, r.text) for r in snap.rules]
    kb._next_rule_id = snap.next_rule_id
    kb.attributes = set(snap.attributes)
    kb._cond_attrs = set(snap.cond_attrs)
    kb._concl_attrs = set(snap.concl_attrs)

# ========= Interface com menu =========
# ====== MENU (substitua o bloco MENU inteiro por este) ======
MENU = [
    ("adicionar fato",       "af", "Adicionar fato escolhendo variável do catálogo (apenas variáveis de CONDIÇÃO)"),
    ("adicionar regra",      "ar", "Adicionar regra (SE ... ENTÃO ...)"),
    ("listar fatos",         "lf", "Listar fatos"),
    ("listar regras",        "lr", "Listar regras"),
    ("listar variáveis",     "lv", "Listar variáveis derivadas das regras"),
    ("remover fato",         "rf", "Remover fato por atributo"),
    ("remover regra",        "rr", "Remover regra por ID"),
    ("inferir forward",      "fw", "Encadeamento para frente"),
    ("provar",               "bk", "Provar objetivo (picker de variável-alvo e valor)"),
    ("por que",              "pq", "Explanação: Por quê?"),
    ("salvar",               "sv", "Salvar Base de Conhecimento (formato .json)"),
    ("carregar",             "ld", "Carregar Base de Conhecimento (formato: .json)"),
    ("importar regras .txt", "rt", "Importar regras de um arquivo .txt (SE ... ENTÃO ...)"),
    ("desfazer",             "sd", "Desfazer última operação"),
    ("ajuda",                "h",  "Mostrar ajuda de todos os comandos"),
    ("sair",                 "q",  "Sair"),
]

# ====== HELP_EXAMPLES (remova a linha do "como") ======
HELP_EXAMPLES = {
    "adicionar fato": "Escolha uma variável listada e informe o valor",
    "adicionar regra": "SE ... ENTÃO",
    "provar": "Selecione a variável-objetivo e um valor sugerido",
    "por que": "Risk_Level = High",
    "remover fato": "Temperatura",
    "remover regra": "3",
    "salvar": "kb.json (ou deixe vazio para usar kb.json)",
    "carregar": "kb.json (ou deixe vazio para usar kb.json)",
    "importar regras .txt": "regras.txt (uma regra por linha; linhas iniciadas com # ou // são ignoradas)",
}

def print_menu(kb: 'KnowledgeBase'):
    # ----- bloco de status -----
    n_rules = len(kb.rules)
    n_facts = len(kb.facts)

    print("\n################ Estado atual da Base ################")
    print(f"- {n_rules} regra(s) adicionada(s)")
    print(f"- {n_facts} fato(s) adicionados")

    if n_rules == 0 and n_facts == 0:
        print("  (Nenhuma regra e nenhum fato ainda — use 'adicionar regra' (2) ou 'adicionar fato' (1) para começar.)")
    elif n_rules == 0:
        print("  (Nenhuma regra ainda — adicione a primeira com 'adicionar regra' (2).)")
    elif n_facts == 0:
        print("  (Nenhum fato ainda — adicione o primeiro com 'adicionar fato' (1).)")

    # ----- menu de comandos -----
    print("\n=== Agente Baseado em Conhecimento ===")
    for i, (name, alias, desc) in enumerate(MENU, start=1):
        print(f"{i:>2}. {name:<20} [{alias}] - {desc}")
    print("Digite número, alias (ex.: 'af'), ou parte do nome (ex.: 'sal'). 'h' mostra exemplos.\n")

def prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""

def confirm(msg: str) -> bool:
    ans = prompt(f"{msg} [s/N]: ").lower()
    return ans in ("s", "sim", "y", "yes")

def resolve_command(user: str) -> Optional[str]:
    s = user.strip().lower()
    if not s:
        return None
    if s.isdigit():
        idx = int(s) - 1
        if 0 <= idx < len(MENU):
            return MENU[idx][0]
        return None
    for name, alias, _ in MENU:
        if s == alias:
            return name
    for name, _, _ in MENU:
        if s == name:
            return name
    candidates = [name for name, _, _ in MENU]
    m = difflib.get_close_matches(s, candidates, n=1, cutoff=0.5)
    return m[0] if m else None

# ========= Importador de regras .txt =========

def load_rules_from_txt(kb: KnowledgeBase, path: str) -> Tuple[int, List[str]]:
    added = 0
    errors: List[str] = []

    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo '{path}' não existe.")

    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#") or line.startswith("//"):
                continue
            if line.endswith(";"):
                line = line[:-1].strip()
            try:
                conds, concl = parse_rule_pt(line)
                kb.add_rule(conds, concl, text=line)
                added += 1
            except Exception as e:
                errors.append(f"Linha {lineno}: {e} | Conteúdo: {raw.rstrip()}")

    return added, errors

# ========= Pickers =========

def pick_from_list(options: List[str], header: str) -> Optional[str]:
    if not options:
        print("(sem opções)")
        return None
    print(header)
    for i, a in enumerate(options, start=1):
        print(f"{i:>2}. {a}")
    s = prompt("Escolha pelo número, digite o nome (ou parte), ou ENTER p/ cancelar: ")
    if not s:
        return None
    s_low = s.lower()

    if s_low.isdigit():
        idx = int(s_low) - 1
        if 0 <= idx < len(options):
            return options[idx]
        print("[ERRO] Índice inválido.")
        return None

    # match exato
    for a in options:
        if s == a:
            return a

    # substring / fuzzy
    partial = [a for a in options if s_low in a.lower()]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        print("Vários candidatos encontrados:")
        for i, a in enumerate(partial, start=1):
            print(f"{i:>2}. {a}")
        s2 = prompt("Escolha pelo número, ou ENTER p/ cancelar: ")
        if s2 and s2.isdigit():
            j = int(s2) - 1
            if 0 <= j < len(partial):
                return partial[j]
        return None

    m = difflib.get_close_matches(s, options, n=3, cutoff=0.6)
    if m:
        print("Você quis dizer:")
        for i, a in enumerate(m, start=1):
            print(f"{i:>2}. {a}")
        s3 = prompt("Escolha pelo número ou ENTER p/ cancelar: ")
        if s3 and s3.isdigit():
            k = int(s3) - 1
            if 0 <= k < len(m):
                return m[k]
    return None

# ========= Handlers =========

def handle_add_fact(kb: KnowledgeBase, undo_stack: List['Snapshot']):
    attrs = kb.get_attributes_for_facts()
    if not attrs:
        print("( Não há variáveis de condição derivadas de regras ainda. )")
        return

    print("\nVariáveis disponíveis para fato (CONDIÇÕES):")
    for i, a in enumerate(attrs, start=1):
        print(f"{i:>2}. {a}")
    attr = pick_from_list(attrs, header="\nSelecione a variável do fato:")
    if attr is None:
        print("Cancelado.")
        return

    # Mostrar valores de exemplo (das condições)
    examples = kb.get_example_values_for_attr(attr, max_n=5)
    if examples:
        print(f"Exemplos de valores para '{attr}' (das regras): {examples}")

    val_raw = prompt(f"Valor para {attr}: ")
    if not val_raw:
        print("Cancelado.")
        return
    try:
        val = parse_value(val_raw)
    except Exception:
        val = val_raw
    undo_stack.append(snapshot_kb(kb))
    kb.add_fact(attr, val)
    print(f"[OK] Fato adicionado: {attr} = {val}")

def handle_add_rule(kb: KnowledgeBase, undo_stack: List['Snapshot']):
    ex = HELP_EXAMPLES["adicionar regra"]
    payload = prompt(f"Informe regra ({ex}): ")
    if not payload:
        print("Cancelado.")
        return
    try:
        conds, concl = parse_rule_pt(payload)
    except Exception as e:
        print(f"[ERRO] {e}")
        return
    undo_stack.append(snapshot_kb(kb))
    rid = kb.add_rule(conds, concl, text=payload.strip())
    print(f"[OK] Regra #{rid} adicionada.")

def handle_list_facts(kb: KnowledgeBase):
    facts = kb.list_facts()
    if not facts:
        print("(sem fatos)")
        return
    for i, f in enumerate(facts, start=1):
        print(f"{i:>2}. {f.attr} = {f.value}")

def handle_list_rules(kb: KnowledgeBase):
    rules = kb.list_rules()
    if not rules:
        print("(sem regras)")
        return
    for r in rules:
        lhs = " E ".join([f"{c['attr']} {c['op']} {c['value']}" for c in r.conditions])
        rhs = f"{r.conclusion['attr']} = {r.conclusion['value']}"
        print(f"- Regra #{r.id}: SE {lhs} ENTÃO {rhs}")

def handle_list_vars(kb: KnowledgeBase):
    attrs = kb.get_attributes()
    cond_attrs = kb.get_attributes_for_facts()
    concl_attrs = kb.get_conclusion_attributes()
    if attrs:
        print("Variáveis conhecidas (todas):")
        for i, a in enumerate(attrs, start=1):
            print(f"{i:>2}. {a}")
        print("\nPara adicionar fatos (picker), são usadas APENAS as variáveis de CONDIÇÕES:")
        print(" - " + (", ".join(cond_attrs) if cond_attrs else "(nenhuma)"))
        if concl_attrs:
            print("\nVariáveis que aparecem como CONCLUSÕES:")
            print(" - " + ", ".join(concl_attrs))
    else:
        print("(sem variáveis derivadas; adicione ou carregue regras)")

def handle_remove_fact(kb: KnowledgeBase, undo_stack: List['Snapshot']):
    attr = pick_fact_attr(kb)
    if not attr:
        print("Cancelado.")
        return
    val = kb.facts.get(attr)
    if not confirm(f"Remover fato '{attr} = {val}'?"):
        print("Cancelado.")
        return
    undo_stack.append(snapshot_kb(kb))
    del kb.facts[attr]
    kb.justifications.pop(attr, None)
    print(f"[OK] Fato removido: {attr}")


def handle_remove_rule(kb: KnowledgeBase, undo_stack: List['Snapshot']):
    rid_s = prompt("ID da regra a remover (ex.: 3): ")
    if not rid_s or not rid_s.isdigit():
        print("[ERRO] Informe um ID numérico.")
        return
    rid = int(rid_s)
    if not any(r.id == rid for r in kb.rules):
        print(f"[ERRO] Regra #{rid} não encontrada.")
        return
    if not confirm(f"Remover Regra #{rid}?"):
        print("Cancelado.")
        return
    undo_stack.append(snapshot_kb(kb))
    kb.remove_rule(rid)
    print(f"[OK] Regra #{rid} removida.")

def handle_forward(kb: KnowledgeBase, undo_stack: List['Snapshot']):
    undo_stack.append(snapshot_kb(kb))
    inferred = forward_chain(kb)
    if not inferred:
        print("Nenhum novo fato inferido.")
    else:
        for f in inferred:
            print(f"[NEW] {f.attr} = {f.value}")

def handle_backward(kb: KnowledgeBase, undo_stack: List['Snapshot']):
    concl_attrs = kb.get_conclusion_attributes()
    if not concl_attrs:
        print("(Não há variáveis-objetivo derivadas de conclusões ainda.)")
        return

    goal_attr = pick_from_list(concl_attrs, header="\nVariáveis-objetivo disponíveis (CONCLUSÕES):")
    if goal_attr is None:
        print("Cancelado.")
        return

    values = kb.get_goal_values_for_attr(goal_attr)
    if values:
        print(f"\nValores possíveis para '{goal_attr}' (das regras):")
        for i, v in enumerate(values, start=1):
            print(f"{i:>2}. {v}")
        s = prompt("Escolha pelo número, digite um valor manualmente (ex.: High), ou ENTER p/ cancelar: ")
        if not s:
            print("Cancelado.")
            return
        if s.isdigit():
            idx = int(s) - 1
            if 0 <= idx < len(values):
                goal_val = values[idx]
            else:
                print("[ERRO] Índice inválido.")
                return
        else:
            goal_val = parse_value(s)
    else:
        raw = prompt(f"Valor objetivo para {goal_attr}: ")
        if not raw:
            print("Cancelado.")
            return
        goal_val = parse_value(raw)

    undo_stack.append(snapshot_kb(kb))
    ok = backward_prove(kb, goal_attr, goal_val)
    print(f"[Objetivo] {goal_attr} = {goal_val} -> " + ("[SIM]" if ok else "[NÃO]"))


def handle_how(kb: KnowledgeBase):
    sel = pick_fact_pair(kb, header="\nFatos disponíveis para explicar 'como':")
    if not sel:
        print("Cancelado.")
        return
    attr, val = sel
    print("\n= Como foi derivado =")
    print(explain_how(kb, attr, val))

def handle_why(kb: KnowledgeBase):
    sel = pick_fact_pair(kb, header="\nFatos disponíveis para explicar 'por que':")
    if not sel:
        print("Cancelado.")
        return
    attr, val = sel
    print("\n= Por que isso é verdade =")
    print(explain_why(kb, attr, val))
    
def handle_save(kb: KnowledgeBase):
    path = prompt("Nome do arquivo (sem extensão) [default: kb]: ") or "kb"
    # garante extensão .json
    if not path.lower().endswith(".json"):
        path += ".json"

    if os.path.exists(path):
        if not confirm(f"Arquivo '{path}' já existe. Sobrescrever?"):
            print("Cancelado.")
            return

    with open(path, "w", encoding="utf-8") as f:
        json.dump(kb.to_json(), f, ensure_ascii=False, indent=2)
    print(f"[OK] KB salva em {path}")


def handle_load(kb: KnowledgeBase, undo_stack: List['Snapshot']):
    path = prompt("Arquivo para carregar (formato deve ser: .json) [default: kb.json]: ") or "kb.json"
    if not os.path.exists(path):
        print(f"[ERRO] Arquivo '{path}' não existe.")
        return
    if not confirm(f"Carregar Base de '{path}'? (substituirá base atual)"):
        print("Cancelado.")
        return
    undo_stack.append(snapshot_kb(kb))
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    kb.load_json(obj)
    print(f"[OK] KB carregada de {path}")

def handle_import_rules_txt(kb: KnowledgeBase, undo_stack: List['Snapshot']):
    path = prompt("Arquivo .txt com regras [default: regras.txt]: ") or "regras.txt"
    if not os.path.exists(path):
        print(f"[ERRO] Arquivo '{path}' não existe.")
        return
    if not confirm(f"Importar regras de '{path}' para a KB atual?"):
        print("Cancelado.")
        return
    undo_stack.append(snapshot_kb(kb))
    try:
        added, errors = load_rules_from_txt(kb, path)
        print(f"[OK] {added} regra(s) importada(s).")
        if errors:
            print("[AVISOS] Algumas linhas não foram importadas:")
            for e in errors:
                print(" -", e)
    except Exception as e:
        print(f"[ERRO] Falha ao importar: {e}")

def handle_undo(kb: KnowledgeBase, undo_stack: List['Snapshot']):
    if not undo_stack:
        print("Nada a desfazer.")
        return
    snap = undo_stack.pop()
    restore_kb(kb, snap)
    print("[OK] Desfeito.")

def show_help_all():
    print("\n=== Ajuda Rápida ===")
    for name, alias, desc in MENU:
        ex = HELP_EXAMPLES.get(name, "")
        ex_str = f" | Ex.: {ex}" if ex else ""
        print(f"- {name:<20} [{alias}] - {desc}{ex_str}")
    print()
    
def pick_fact_attr(kb: KnowledgeBase, header: str = "\nFatos atuais (escolha um para remover):") -> Optional[str]:
    if not kb.facts:
        print("(sem fatos na KB)")
        return None
    attrs = sorted(kb.facts.keys())
    print(header)
    for i, a in enumerate(attrs, start=1):
        print(f"{i:>2}. {a} = {kb.facts[a]}")
    s = prompt("Escolha pelo número, digite o nome (ou parte), ou ENTER p/ cancelar: ").strip()
    if not s:
        return None
    s_low = s.lower()

    # número?
    if s_low.isdigit():
        idx = int(s_low) - 1
        if 0 <= idx < len(attrs):
            return attrs[idx]
        print("[ERRO] Índice inválido.")
        return None

    # match exato
    for a in attrs:
        if s == a:
            return a

    # substring / fuzzy
    parcial = [a for a in attrs if s_low in a.lower()]
    if len(parcial) == 1:
        return parcial[0]
    if len(parcial) > 1:
        print("Vários candidatos encontrados:")
        for i, a in enumerate(parcial, start=1):
            print(f"{i:>2}. {a} = {kb.facts[a]}")
        s2 = prompt("Escolha pelo número, ou ENTER p/ cancelar: ")
        if s2 and s2.isdigit():
            j = int(s2) - 1
            if 0 <= j < len(parcial):
                return parcial[j]
        return None

    import difflib
    m = difflib.get_close_matches(s, attrs, n=3, cutoff=0.6)
    if m:
        print("Você quis dizer:")
        for i, a in enumerate(m, start=1):
            print(f"{i:>2}. {a} = {kb.facts[a]}")
        s3 = prompt("Escolha pelo número, ou ENTER p/ cancelar: ")
        if s3 and s3.isdigit():
            k = int(s3) - 1
            if 0 <= k < len(m):
                return m[k]
    return None


# === [N O V O] Diagnóstico quando a prova falha ===
def diagnose_backward_failure(kb: KnowledgeBase, goal_attr: str, goal_val: Any) -> None:
    print("\n= Diagnóstico da falha de prova =")
    # Quais regras poderiam concluir o objetivo?
    candidates = [r for r in kb.rules
                  if r.conclusion.get("attr") == goal_attr and r.conclusion.get("value") == goal_val]
    if not candidates:
        print(f"- Não há regras cuja CONCLUSÃO seja {goal_attr} = {goal_val}.")
        return
    for r in candidates:
        print(f"- Regra #{r.id}: {r.text or '(sem texto)'}")
        for c in r.conditions:
            a, op, v = c["attr"], c["op"], c["value"]
            if a not in kb.facts:
                print(f"   • {a} {op} {v}  -> FALHOU (faltando fato '{a}')")
            else:
                ok = _cmp(kb.facts[a], op, v)
                status = "OK" if ok else f"FALHOU (na KB: {a} = {kb.facts[a]!r})"
                print(f"   • {a} {op} {v}  -> {status}")
    print()

# === [A L T E R A] Handler do 'provar' para explicar automaticamente ===
def handle_backward(kb: KnowledgeBase, undo_stack: List['Snapshot']):
    concl_attrs = kb.get_conclusion_attributes()
    if not concl_attrs:
        print("(Não há variáveis-objetivo derivadas de conclusões ainda.)")
        return

    # 1) Escolher variável-objetivo
    goal_attr = pick_from_list(concl_attrs, header="\nVariáveis-objetivo disponíveis (CONCLUSÕES):")
    if goal_attr is None:
        print("Cancelado.")
        return

    # 2) Sugerir valores possíveis (das conclusões)
    values = kb.get_goal_values_for_attr(goal_attr)
    if values:
        print(f"\nValores possíveis para '{goal_attr}' (das regras):")
        for i, v in enumerate(values, start=1):
            print(f"{i:>2}. {v}")
        s = prompt("Escolha pelo número, digite um valor manualmente (ex.: High), ou ENTER p/ cancelar: ")
        if not s:
            print("Cancelado.")
            return
        if s.isdigit():
            idx = int(s) - 1
            if 0 <= idx < len(values):
                goal_val = values[idx]
            else:
                print("[ERRO] Índice inválido.")
                return
        else:
            goal_val = parse_value(s)
    else:
        raw = prompt(f"Valor objetivo para {goal_attr}: ")
        if not raw:
            print("Cancelado.")
            return
        goal_val = parse_value(raw)

    # 3) Provar
    undo_stack.append(snapshot_kb(kb))
    ok = backward_prove(kb, goal_attr, goal_val)
    print(f"[Objetivo] {goal_attr} = {goal_val} -> " + ("[SIM]" if ok else "[NÃO]"))

    # 4) Explicar automaticamente
    if ok:
        print("\n= Como foi provado =")
        print(explain_how(kb, goal_attr, goal_val))
        # Se preferir estilo "Por quê?" (cadeia com premissas conhecidas), troque para explain_why.
    else:
        diagnose_backward_failure(kb, goal_attr, goal_val)

def list_fact_pairs(kb: KnowledgeBase) -> List[Tuple[str, Any]]:
    # Lista (attr, value) atuais, ordenados por nome do atributo
    return sorted([(f.attr, f.value) for f in kb.list_facts()], key=lambda x: x[0].lower())

def pick_fact_pair(kb: KnowledgeBase, header: str) -> Optional[Tuple[str, Any]]:
    pairs = list_fact_pairs(kb)
    if not pairs:
        print("(sem fatos na KB — nada para explicar)")
        return None
    print(header)
    for i, (a, v) in enumerate(pairs, start=1):
        print(f"{i:>2}. {a} = {v}")
    s = prompt("Escolha pelo número ou ENTER p/ cancelar: ")
    if not s:
        return None
    if s.isdigit():
        idx = int(s) - 1
        if 0 <= idx < len(pairs):
            return pairs[idx]
        print("[ERRO] Índice inválido.")
        return None
    print("[ERRO] Digite apenas o número do item.")
    return None


def main():
    kb = KnowledgeBase()
    undo_stack: List[Snapshot] = []

    # Regras demo (opcional)
    demo_rules: List[str] = []
    for txt in demo_rules:
        conds, concl = parse_rule_pt(txt)
        kb.add_rule(conds, concl, text=txt)

    while True:
        print_menu(kb)
        raw = prompt("> ")
        if raw.lower() in ("h", "help", "ajuda", "?"):
            show_help_all()
            continue
        cmd = resolve_command(raw)
        if not cmd:
            print("Não entendi. Digite número, alias, parte do nome, ou 'h' para ajuda.")
            continue

        if cmd == "sair":
            print("Encerrando.")
            break
        elif cmd == "adicionar fato":
            handle_add_fact(kb, undo_stack)
        elif cmd == "adicionar regra":
            handle_add_rule(kb, undo_stack)
        elif cmd == "listar fatos":
            handle_list_facts(kb)
        elif cmd == "listar regras":
            handle_list_rules(kb)
        elif cmd == "listar variáveis":
            handle_list_vars(kb)
        elif cmd == "remover fato":
            handle_remove_fact(kb, undo_stack)
        elif cmd == "remover regra":
            handle_remove_rule(kb, undo_stack)
        elif cmd == "inferir forward":
            handle_forward(kb, undo_stack)
        elif cmd == "provar":
            handle_backward(kb, undo_stack)
        elif cmd == "por que":
            handle_why(kb) 
        elif cmd == "salvar":
            handle_save(kb)
        elif cmd == "carregar":
            handle_load(kb, undo_stack)
        elif cmd == "importar regras .txt":
            handle_import_rules_txt(kb, undo_stack)
        elif cmd == "desfazer":
            handle_undo(kb, undo_stack)
        elif cmd == "ajuda":
            show_help_all()
            continue

        else:
            print("Comando não mapeado. (bug)")

if __name__ == "__main__":
    main()
