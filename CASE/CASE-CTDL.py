#!/usr/bin/env python3
import json
import uuid
import os
from collections import OrderedDict
from urllib.request import urlopen, Request
from urllib.parse import urlparse
from urllib.error import URLError, HTTPError

CTDLASN_CONTEXT = "https://credreg.net/ctdlasn/schema/context/json"
DEFAULT_REG_BASE = "https://credentialengineregistry.org/resources/"

def _to_str(v):
    """Convert any mixed type into a string."""
    if v is None:
        return ""
    if isinstance(v, (str, int, float, bool)):
        return str(v)
    if isinstance(v, list):
        return "; ".join(_to_str(x) for x in v if _to_str(x))
    if isinstance(v, dict):
        for k in ("title", "name", "label", "value", "text", "displayName", "shortName"):
            if v.get(k):
                return _to_str(v[k])
        for k in ("uri", "CFItemURI", "CFDocumentURI", "identifier", "CFItemGUID"):
            if v.get(k):
                return _to_str(v[k])
        return json.dumps(v, ensure_ascii=False)
    return str(v)

def is_course(item) -> bool:
    return _to_str(item.get("CFItemType")).strip().lower() == "course"

def fetch_json(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Please provide an http(s) URL.")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

def reg_id(base: str, ctid: str) -> str:
    ctid = ctid if ctid.startswith("ce-") else f"ce-{ctid}"
    if not base.endswith("/"):
        base += "/"
    return base + ctid

def build_graphs(pkg, reg_base, output_dir):
    root = pkg.get("CFPackage") or pkg
    cfdoc = root.get("CFDocument") or {}
    items = root.get("CFItems") or []
    assocs = root.get("CFAssociations") or []

    os.makedirs(output_dir, exist_ok=True)

    # Use CASE language exactly as provided (no normalization)
    fw_lang = _to_str(cfdoc.get("language")).strip() if cfdoc.get("language") else None
    fw_doc_uri = cfdoc.get("CFDocumentURI") or cfdoc.get("officialSourceURL") or None
    fw_publisher_name = _to_str(cfdoc.get("publisher")) if cfdoc.get("publisher") else None
    fw_desc_text = _to_str(cfdoc.get("description") or "").strip()

    # Index items and keep input order
    item_by_ident, ordered_idents, item_uri_by_ident = {}, [], {}
    for it in items:
        ident = str(it.get("identifier") or it.get("CFItemGUID") or "").strip()
        if not ident:
            continue
        ordered_idents.append(ident)
        item_by_ident[ident] = it
        item_uri_by_ident[ident] = it.get("uri") or it.get("CFItemURI") or ""

    # Resolve endpoints by GUID only
    def resolve_endpoint(raw):
        if raw is None:
            return None
        if isinstance(raw, dict):
            ident = str(raw.get("identifier") or raw.get("CFItemGUID") or "").strip()
            return ident if ident in item_by_ident else None
        s = str(raw).strip()
        return s if s in item_by_ident else None

    def is_childof_type(t):
        t = _to_str(t).strip().lower().replace(" ", "")
        return t in ("ischildof", "ispartof")

    # Build hierarchy (destination = parent, origin = child) and capture sequenceNumber
    children_of = OrderedDict()  # parent -> [child ...] in input order
    parents_of = {}              # child -> [parent ...]
    seq_for_child = {}           # child -> first sequenceNumber seen
    for a in assocs:
        if not is_childof_type(a.get("associationType")):
            continue
        parent_ident = resolve_endpoint(a.get("destinationNodeURI") or a.get("destinationNodeIdentifier"))
        child_ident  = resolve_endpoint(a.get("originNodeURI")       or a.get("originNodeIdentifier"))
        if not parent_ident or not child_ident:
            continue
        children_of.setdefault(parent_ident, [])
        if child_ident not in children_of[parent_ident]:
            children_of[parent_ident].append(child_ident)
        parents_of.setdefault(child_ident, [])
        if parent_ident not in parents_of[child_ident]:
            parents_of[child_ident].append(parent_ident)
        if "sequenceNumber" in a and child_ident not in seq_for_child:
            seq_for_child[child_ident] = str(a.get("sequenceNumber")).strip()

    # Split: courses vs competencies
    competencies = OrderedDict()
    courses = OrderedDict()

    for ident in ordered_idents:
        it = item_by_ident[ident]
        ce_ctid = ident if ident.startswith("ce-") else f"ce-{ident}"
        ce_atid = reg_id(reg_base, ce_ctid)
        uri = it.get("uri")
        hcs = _to_str(it.get("humanCodingScheme")).strip()

        if is_course(it):
            name = _to_str(it.get("abbreviatedStatement") or it.get("fullStatement") or "").strip()
            desc = _to_str(it.get("fullStatement") or "").strip()
            course_node = {
                "@id": ce_atid,
                "@type": "ceterms:Course",
                "ceterms:ctid": ce_ctid,
            }
            if name:
                course_node["ceterms:name"] = {fw_lang: name} if fw_lang else name
            if desc and desc != name:
                course_node["ceterms:description"] = {fw_lang: desc} if fw_lang else desc
            if hcs:
                course_node["ceterms:codedNotation"] = hcs
            if item_uri_by_ident.get(ident):
                course_node["ceterms:subjectWebpage"] = item_uri_by_ident[ident]
            courses[ident] = course_node
        else:
            comp_node = {
                "@id": ce_atid,
                "@type": "ceasn:Competency",
                "ceterms:ctid": ce_ctid,
            }
            if fw_lang:
                comp_node["ceasn:inLanguage"] = fw_lang
            # Language-mapped fields
            fs = it.get("fullStatement")
            if fs:
                comp_node["ceasn:competencyText"] = {fw_lang: fs} if fw_lang else fs
            abbr = it.get("abbreviatedStatement")
            if abbr:
                comp_node["ceasn:competencyLabel"] = {fw_lang: abbr} if fw_lang else abbr
            cfit = it.get("CFItemType")
            if cfit:
                comp_node["ceasn:competencyCategory"] = {fw_lang: _to_str(cfit)} if fw_lang else _to_str(cfit)
            if hcs:
                comp_node["ceasn:codedNotation"] = hcs
            # listID from source or association sequence
            if it.get("listEnumInSource") is not None:
                comp_node["ceasn:listID"] = _to_str(it.get("listEnumInSource"))
            elif ident in seq_for_child:
                comp_node["ceasn:listID"] = seq_for_child[ident]
            # broadAlignment to CASE URI (as object with the URI key)
            if uri:
                comp_node["ceasn:broadAlignment"] = {uri: ""}
            competencies[ident] = comp_node

    # DFS expand (parent + descendants) in input order
    def expand_competency_subtree(root_guid, seen):
        if root_guid not in competencies or root_guid in seen:
            return []
        seen.add(root_guid)
        ordered = [root_guid]
        for ch in children_of.get(root_guid, []):
            if ch in competencies and ch not in seen:
                ordered.extend(expand_competency_subtree(ch, seen))
        return ordered

    # Build ceterms:teaches for each course (parents + all descendants)
    for course_ident, course_node in courses.items():
        all_targets = []
        seen = set()
        for root_comp in children_of.get(course_ident, []):
            if root_comp in competencies:
                all_targets.extend(expand_competency_subtree(root_comp, seen))
        if all_targets:
            teaches = []
            for guid in all_targets:
                comp = competencies[guid]
                # choose a display name for targetNodeName
                ttext = ""
                if isinstance(comp.get("ceasn:competencyText"), dict) and fw_lang:
                    ttext = comp["ceasn:competencyText"].get(fw_lang, "")
                elif isinstance(comp.get("ceasn:competencyText"), str):
                    ttext = comp["ceasn:competencyText"]
                elif isinstance(comp.get("ceasn:competencyLabel"), dict) and fw_lang:
                    ttext = comp["ceasn:competencyLabel"].get(fw_lang, "")
                elif isinstance(comp.get("ceasn:competencyLabel"), str):
                    ttext = comp["ceasn:competencyLabel"]
                teaches.append({
                    "@type": "ceterms:CredentialAlignmentObject",
                    "ceterms:framework": None,  # filled in the per-course framework pass
                    "ceterms:targetNode": comp["@id"],
                    "ceterms:frameworkName": ({fw_lang: ""} if fw_lang else ""),
                    "ceterms:targetNodeName": ({fw_lang: ttext} if fw_lang else ttext)
                })
            course_node["ceterms:teaches"] = teaches

    # Create one framework JSON per course
    for course_ident, course_node in courses.items():
        course_ctid = course_node["ceterms:ctid"]

        # Deterministic framework CTID from course CTID
        fw_uuid = uuid.uuid5(uuid.NAMESPACE_URL, "framework:" + course_ctid).hex
        fw_ctid = f"ce-{fw_uuid[:8]}-{fw_uuid[8:12]}-{fw_uuid[12:16]}-{fw_uuid[16:20]}-{fw_uuid[20:]}"
        fw_atid = reg_id(reg_base, fw_ctid)

        # Framework name (avoid double-encoding if name already a language map)
        course_name_field = course_node.get("ceterms:name", {})
        if isinstance(course_name_field, dict) and fw_lang in course_name_field:
            fw_name_val = course_name_field[fw_lang]
        else:
            fw_name_val = _to_str(course_name_field)

        fw_node = {
            "@id": fw_atid,
            "@type": "ceasn:CompetencyFramework",
            "ceterms:ctid": fw_ctid,
            "ceasn:name": {fw_lang: fw_name_val} if fw_lang else fw_name_val,
        }
        if fw_lang:
            fw_node["ceasn:inLanguage"] = [fw_lang]
        if fw_doc_uri:
            fw_node["ceterms:subjectWebpage"] = fw_doc_uri
        if fw_publisher_name:
            fw_node["ceasn:publisherName"] = {fw_lang: fw_publisher_name} if fw_lang else fw_publisher_name
        if fw_desc_text:
            fw_node["ceasn:description"] = {fw_lang: fw_desc_text} if fw_lang else fw_desc_text

        # Direct children of course are top children (parents) in order
        parent_roots = [c for c in children_of.get(course_ident, []) if c in competencies]
        fw_node["ceasn:hasTopChild"] = [
            reg_id(reg_base, (p if p.startswith("ce-") else f"ce-{p}"))
        for p in parent_roots] if parent_roots else []

        # Build subtree (parents + descendants)
        subtree = []
        seen = set()
        for root in parent_roots:
            subtree.extend(expand_competency_subtree(root, seen))

        # Clone competencies into this framework; rebuild local relationships
        comp_nodes = OrderedDict()
        for guid in subtree:
            base = competencies[guid]
            node_copy = dict(base)
            # ceasn:isPartOf (replace inFramework)
            node_copy["ceasn:isPartOf"] = fw_atid
            # ensure @id remains the registry id already set
            comp_nodes[guid] = node_copy

        # Add local hasChild and reciprocal isChildOf
        for guid, node in comp_nodes.items():
            local_children = [c for c in children_of.get(guid, []) if c in comp_nodes]
            if local_children:
                node["ceasn:hasChild"] = [comp_nodes[c]["@id"] for c in local_children]
                for child_guid in local_children:
                    child_node = comp_nodes[child_guid]
                    parent_id = node["@id"]
                    if "ceasn:isChildOf" not in child_node:
                        child_node["ceasn:isChildOf"] = []
                    if parent_id not in child_node["ceasn:isChildOf"]:
                        child_node["ceasn:isChildOf"].append(parent_id)

        # Fill course's teaches.framework + frameworkName now that framework exists
        if "ceterms:teaches" in course_node:
            for aln in course_node["ceterms:teaches"]:
                aln["ceterms:framework"] = fw_atid
                aln["ceterms:frameworkName"] = fw_node["ceasn:name"]

        # Write one JSON per framework
        graph = {
            "@context": CTDLASN_CONTEXT,
            "@id": fw_atid,
            "@graph": [fw_node] + list(comp_nodes.values())
        }
        filename = os.path.join(output_dir, f"framework_{course_ctid}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)

    return courses

def main():
    try:
        url = input("Enter CASE CFPackage URL: ").strip()
        output_dir = input("Output folder for frameworks [frameworks_out]: ").strip() or "frameworks_out"
        out_courses = input("Courses output [courses.json]: ").strip() or "courses.json"
        reg_base = input(f"Registry base URL [{DEFAULT_REG_BASE}]: ").strip() or DEFAULT_REG_BASE

        print("Fetching CASE package...")
        pkg = fetch_json(url)
        print("Building individual course frameworks + courses...")
        courses = build_graphs(pkg, reg_base, output_dir)

        # Write combined courses.json
        course_graph = {"@context": CTDLASN_CONTEXT, "@graph": list(courses.values())}
        with open(out_courses, "w", encoding="utf-8") as f:
            json.dump(course_graph, f, ensure_ascii=False, indent=2)

        print(f"Created {len(courses)} framework JSON files in '{output_dir}'")
        print(f"Wrote {len(courses)} courses to {out_courses}")
    except (HTTPError, URLError) as e:
        print(f"Network/HTTP error: {e}")
    except json.JSONDecodeError as e:
        print(f"Invalid JSON at source: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
