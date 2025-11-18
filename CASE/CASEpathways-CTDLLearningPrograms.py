#!/usr/bin/env python3
import json
import os
from collections import OrderedDict
from urllib.request import urlopen, Request
from urllib.parse import urlparse
from urllib.error import URLError, HTTPError

# Contexts
CTDL_CONTEXT = "https://credreg.net/ctdl/schema/context/json"
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


def is_pathway(item) -> bool:
    return _to_str(item.get("CFItemType")).strip().lower() == "pathway"

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


def is_registry_ce_uri(value: str, reg_base: str = DEFAULT_REG_BASE) -> bool:
    """Check registry URI that ends with ce- GUID."""
    if not isinstance(value, str):
        return False
    if not value.startswith("http"):
        return False
    return value.startswith(reg_base + "ce-")


def extract_ctid(value: str) -> str:
    """Return a ce-... CTID from a CE registry URI or raw CTID; add ce- if missing."""
    if not value:
        return ""
    s = value.strip()
    if s.startswith("http"):
        tail = s.rstrip("/").split("/")[-1]
        return tail if tail.startswith("ce-") else tail
    return s if s.startswith("ce-") else f"ce-{s}"


def parse_ctids_to_registry_uris(raw: str, reg_base: str = DEFAULT_REG_BASE):
    """Comma-separated CTIDs/URIs -> list of CE registry URIs."""
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    uris = []
    for p in parts:
        if p.startswith("http"):
            uris.append(p)
        else:
            uris.append(reg_id(reg_base, p))
    return uris


def parse_publisher_list(raw: str, reg_base: str = DEFAULT_REG_BASE):
 
    uris = parse_ctids_to_registry_uris(raw, reg_base)
    first_ctid = extract_ctid(uris[0]) if uris else ""
    return uris, first_ctid


def yes_no(prompt: str) -> bool:
    ans = input(prompt + " [y/N]: ").strip().lower()
    return ans in ("y", "yes")


# --------------------------------------------------------------------------------------
# Pathway mapping
# --------------------------------------------------------------------------------------

def build_pathways(
    pkg,
    publisher_uris,
    publisher_ctid,
    owned_by_list,
    offered_by_list,
    reg_base=DEFAULT_REG_BASE,
    learningprograms_outdir="learningprograms_out",
    validations_outfile="validations_pathways.json"
):
   
    root = pkg.get("CFPackage") or pkg
    cfdoc = root.get("CFDocument") or {}
    # Be flexible: CFItems or CFItem; CFAssociations or CFAssociation
    items = root.get("CFItems") or root.get("CFItem") or []
    assocs = root.get("CFAssociations") or root.get("CFAssociation") or []

    os.makedirs(learningprograms_outdir, exist_ok=True)

    # Language similar to your course script
    raw_lang = _to_str(cfdoc.get("language")).strip() if cfdoc.get("language") else None
    if raw_lang and raw_lang.lower() == "eng":
        lp_lang = "en"
    else:
        lp_lang = raw_lang

    # Index items
    item_by_ident = {}
    ordered_idents = []
    item_uri_by_ident = {}

    for it in items:
        ident = str(it.get("identifier") or it.get("CFItemGUID") or "").strip()
        if not ident:
            continue
        ordered_idents.append(ident)
        item_by_ident[ident] = it
        item_uri_by_ident[ident] = it.get("uri") or it.get("CFItemURI") or ""

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

    # Identify courses and pathways
    course_idents = set()
    pathway_idents = set()

    for ident in ordered_idents:
        it = item_by_ident[ident]
        if is_course(it):
            course_idents.add(ident)
        elif is_pathway(it):
            pathway_idents.add(ident)

    # Build parent->children and child->parents maps based on isChildOf/isPartOf
    children_of = OrderedDict()
    parents_of = OrderedDict()
    for a in assocs:
        if not is_childof_type(a.get("associationType")):
            continue
        parent_ident = resolve_endpoint(a.get("destinationNodeURI") or a.get("destinationNodeIdentifier"))
        child_ident  = resolve_endpoint(a.get("originNodeURI") or a.get("originNodeIdentifier"))
        if not parent_ident or not child_ident:
            continue
        children_of.setdefault(parent_ident, [])
        if child_ident not in children_of[parent_ident]:
            children_of[parent_ident].append(child_ident)
        parents_of.setdefault(child_ident, [])
        if parent_ident not in parents_of[child_ident]:
            parents_of[child_ident].append(parent_ident)

    # Validation report structure
    validation_report = {
        "learningPrograms": [],
        "summary": {}
    }

    def add_lp_validation(lp_node, errors):
        if errors:
            validation_report["learningPrograms"].append({
                "@id": lp_node.get("@id"),
                "errors": errors
            })

    # validations
    def validate_learning_program(lp_node):
        errs = []
        if not lp_node.get("ceterms:ctid"):
            errs.append("Missing ceterms:ctid")
        nm = lp_node.get("ceterms:name")
        if not nm or (isinstance(nm, dict) and not any(nm.values())):
            errs.append("Missing ceterms:name")
        if not lp_node.get("ceterms:inLanguage"):
            errs.append("Missing ceterms:inLanguage")
        if not lp_node.get("ceterms:lifeCycleStatusType"):
            errs.append("Missing ceterms:lifeCycleStatusType")
        owned = lp_node.get("ceterms:ownedBy")
        offered = lp_node.get("ceterms:offeredBy")
        if not owned and not offered:
            errs.append("Missing ceterms:ownedBy or ceterms:offeredBy (one required)")
        is_prep_for = lp_node.get("ceterms:isPreparationFor")
        if not is_prep_for:
            errs.append("Missing ceterms:isPreparationFor")
        return errs

    # Constant ConditionProfile metadata
    CONDITION_PROFILE_NAME = "Is Preparation For"
    CONDITION_PROFILE_DESC = (
        "Students who complete this CTAE pathway will be prepared to earn the following courses of value."
    )
    # Constant lifecycle object to attach to every course
    lifecycle_alignment = {
        "@type": "ceterms:CredentialAlignmentObject",
        "ceterms:framework": "https://credreg.net/ctdl/terms/LifeCycleStatus",
        "ceterms:targetNode": "lifeCycle:Active",
        "ceterms:frameworkName": {"en-US": "Life Cycle Status"},
        "ceterms:targetNodeName": {"en-US": "Active"},
        "ceterms:targetNodeDescription": {
            "en-US": "Resource is active, current, ongoing, offered, operational, or available."
        }
    }

    total_lps = 0

    for pathway_ident in pathway_idents:
        it = item_by_ident[pathway_ident]
        ce_ctid = pathway_ident if pathway_ident.startswith("ce-") else f"ce-{pathway_ident}"
        ce_atid = reg_id(reg_base, ce_ctid)

        name = _to_str(it.get("abbreviatedStatement") or it.get("fullStatement") or "").strip()
        notes = _to_str(it.get("notes") or "").strip()
        full_statement = _to_str(it.get("fullStatement") or "").strip()

        description = notes or full_statement or ""

        lp_node = {
            "@id": ce_atid,
            "@type": "ceterms:LearningProgram",
            "ceterms:ctid": ce_ctid,
            "ceterms:lifeCycleStatusType": lifecycle_alignment,
        }

        # orgs
        if owned_by_list:
            lp_node["ceterms:ownedBy"] = owned_by_list
        if offered_by_list:
            lp_node["ceterms:offeredBy"] = offered_by_list

        # language
        if lp_lang:
            lp_node["ceterms:inLanguage"] = [lp_lang]

        # name / description
        if name:
            lp_node["ceterms:name"] = {lp_lang: name} if lp_lang else name
        if description:
            lp_node["ceterms:description"] = {lp_lang: description} if lp_lang else description

        # subjectWebpage 
        if item_uri_by_ident.get(pathway_ident):
            lp_node["ceterms:subjectWebpage"] = item_uri_by_ident[pathway_ident]
        
        #find associated courses
        course_targets = set()

        for parent_ident in parents_of.get(pathway_ident, []):
            for child_ident in children_of.get(parent_ident, []):
                if child_ident in course_idents:
                    course_targets.add(child_ident)

        for child_ident in children_of.get(pathway_ident, []):
            if child_ident in course_idents:
                course_targets.add(child_ident)

        #ceterms:isPreparationFor 
        if course_targets:
            target_course_uris = []
            for cid in sorted(course_targets):
                ctid = cid if cid.startswith("ce-") else f"ce-{cid}"
                target_course_uris.append(reg_id(reg_base, ctid))

            condition_profile = {
                "@type": "ceterms:ConditionProfile",
                "ceterms:name": {"en-US": CONDITION_PROFILE_NAME},
                "ceterms:description": {"en-US": CONDITION_PROFILE_DESC},
                "ceterms:targetLearningOpportunity": target_course_uris
            }

            lp_node["ceterms:isPreparationFor"] = [condition_profile]

        # Validate
        errs = validate_learning_program(lp_node)
        add_lp_validation(lp_node, errs)

        # Wrap for Publish
        lp_graph_single = {
            "@context": CTDL_CONTEXT,
            "@id": lp_node["@id"],
            "@graph": [lp_node]
        }
        publish_wrapper_lp = {
            "PublishForOrganizationIdentifier": publisher_ctid,
            "GraphInput": lp_graph_single
        }

        out_filename = os.path.join(
            learningprograms_outdir,
            f"learningprogram_{ce_ctid}.json"
        )
        with open(out_filename, "w", encoding="utf-8") as f:
            json.dump(publish_wrapper_lp, f, ensure_ascii=False, indent=2)

        total_lps += 1

    # Summary
    lp_err_count = len(validation_report["learningPrograms"])
    validation_report["summary"] = {
        "learning_program_count": total_lps,
        "learning_program_error_count": lp_err_count,
    }

    with open(validations_outfile, "w", encoding="utf-8") as f:
        json.dump(validation_report, f, ensure_ascii=False, indent=2)

    return validation_report


def main():
    learningprograms_outdir = "learningprograms_out"
    validations_outfile = "validations_pathways.json"
    reg_base = DEFAULT_REG_BASE

    try:
        url = input("Enter CASE CFPackage URL (vext): ").strip()

        publisher_raw = input(
            "Enter publisher CTID(s) (comma-separated; e.g., ce-123..., 123..., or full CE URIs): "
        ).strip()

        owned_by_raw = input(
            "Enter ownedBy CTID(s) for learning programs (comma-separated; ce-... or ... or full CE URIs). "
            "Leave blank if none: "
        ).strip()

        add_offered = yes_no("Do you want to add offeredBy?")
        offered_by_raw = ""
        if add_offered:
            offered_by_raw = input(
                "Enter offeredBy CTID(s) for learning programs (comma-separated; ce-... or ... or full CE URIs): "
            ).strip()

        publisher_uris, publisher_ctid = parse_publisher_list(publisher_raw, reg_base)
        owned_by_list = parse_ctids_to_registry_uris(owned_by_raw, reg_base)
        offered_by_list = parse_ctids_to_registry_uris(offered_by_raw, reg_base) if add_offered else []

        # Guards
        if not publisher_uris:
            raise ValueError("You must provide at least one publisher CTID/URI.")
        if not publisher_ctid:
            raise ValueError("Could not extract a valid publisher CTID for the graph wrapper.")
        if not owned_by_list and not offered_by_list:
            raise ValueError("You must provide at least one of ownedBy or offeredBy.")

        print("Fetching CASE package...")
        pkg = fetch_json(url)
        print("Creating LearningProgram JSON files for Pathways...")

        validation_report = build_pathways(
            pkg=pkg,
            publisher_uris=publisher_uris,
            publisher_ctid=publisher_ctid,
            owned_by_list=owned_by_list,
            offered_by_list=offered_by_list,
            reg_base=reg_base,
            learningprograms_outdir=learningprograms_outdir,
            validations_outfile=validations_outfile,
        )

        summary = validation_report["summary"]
        print(f"Created {summary['learning_program_count']} LearningProgram JSON files in '{learningprograms_outdir}'")
        print("— Validation summary —")
        print(f"LearningProgram errors: {summary['learning_program_error_count']}")
        if summary['learning_program_error_count']:
            print(f"Validation details saved to {validations_outfile}")

    except (HTTPError, URLError) as e:
        print(f"Network/HTTP error: {e}")
    except json.JSONDecodeError as e:
        print(f"Invalid JSON at source: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
