"""
cleaner.py — JSON pruning and flattening service
==================================================
Migrated exactly from the original ap.py
"""

import hashlib
import json
import re

# Set of exact key names to completely remove from the JSON structure
KEYS_TO_REMOVE = {
    'avatarUrl', 'isDescriptionAdded', 'isActive', 'lastFinalSyncedAt',
    'createdAt', 'updatedAt', 'platformLinks', 'explanation',
    'excludedPlatforms', 'metricPaths', 'hasGender', 'hasCountries',
    'excludeReason', 'sourcePlatform', 'haSync', 'finalSync',
    'calculatedAt', 'providers', 'recentMedia', 'hasAge', 'excluded', 'metricPath',
    'brandMatch',  # This is an internal duplicate of matchExplanation
    'success', 'message'  # Root level response metadata
}

camel_case_regex = re.compile(r'([a-z0-9])([A-Z])')


def humanize(name):
    """Converts snake_case and camelCase into readable Title Case."""
    if not name:
        return ""
    s = camel_case_regex.sub(r'\1 \2', str(name))
    s = s.replace('_', ' ').replace('-', ' ').strip()
    words = s.split()
    if words:
        words[0] = words[0].capitalize()
    return ' '.join(words)


def format_scalar(val):
    """Formats primitive values for text output."""
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "yes" if val else "no"
    return str(val)


def is_empty_or_zero(v):
    """Checks if a value should be considered empty, null, or zero, and thus removed."""
    if v is None:
        return True
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return v == 0
    if isinstance(v, str):
        s = v.strip()
        if not s or s in ("[]", "{}", "()"):
            return True
        if s in ("0", "0.0", "0.00", "-0", "+0"):
            return True
        try:
            return float(s) == 0.0
        except ValueError:
            return False
    if isinstance(v, (list, dict, tuple)):
        return len(v) == 0
    return False

def remove_blacklisted_keys(obj):
    """Recursively removes any dictionary key that exists in the KEYS_TO_REMOVE set."""
    if isinstance(obj, dict):
        # Special handling for finalScore: remove id and athleteId
        if 'finalScore' in obj and isinstance(obj['finalScore'], dict):
            obj['finalScore'].pop('id', None)
            obj['finalScore'].pop('athleteId', None)
        return {
            k: remove_blacklisted_keys(v) 
            for k, v in obj.items() if k not in KEYS_TO_REMOVE
        }
    elif isinstance(obj, list):
        return [remove_blacklisted_keys(item) for item in obj]
    return obj

def prune_empty_and_zero(obj):
    """Recursively removes keys with empty/null/zero values."""
    if isinstance(obj, dict):
        cleaned_dict = {}
        for k, v in obj.items():
            cleaned_val = prune_empty_and_zero(v)
            if not is_empty_or_zero(cleaned_val):
                cleaned_dict[k] = cleaned_val
        return cleaned_dict
        
    elif isinstance(obj, list):
        cleaned_list = []
        for item in obj:
            cleaned_item = prune_empty_and_zero(item)
            if not is_empty_or_zero(cleaned_item):
                cleaned_list.append(cleaned_item)
        return cleaned_list
    else:
        return obj

def get_hash(v):
    """Creates a consistent hash for a JSON-serializable object."""
    return hashlib.sha1(json.dumps(v, sort_keys=True, default=str).encode()).hexdigest()

def deduplicate_subtrees(obj, seen_hashes):
    """Recursively removes duplicate dictionaries and lists."""
    if isinstance(obj, dict):
        cleaned_dict = {}
        for k, v in obj.items():
            cleaned_val = deduplicate_subtrees(v, seen_hashes)
            if isinstance(cleaned_val, (dict, list)):
                h = get_hash(cleaned_val)
                if h in seen_hashes:
                    continue
                else:
                    seen_hashes.add(h)
            cleaned_dict[k] = cleaned_val
        return cleaned_dict
        
    elif isinstance(obj, list):
        cleaned_list = []
        for item in obj:
            cleaned_item = deduplicate_subtrees(item, seen_hashes)
            if isinstance(cleaned_item, (dict, list)):
                h = get_hash(cleaned_item)
                if h in seen_hashes:
                    continue
                else:
                    seen_hashes.add(h)
            cleaned_list.append(cleaned_item)
        return cleaned_list
    else:
        return obj

def dedup_sibling_values(obj):
    """Removes sibling keys that have the exact same value."""
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            obj[k] = dedup_sibling_values(obj[k])
            
        seen_values = {}
        keys_to_drop = []
        
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                val_sig = ('hash', get_hash(v))
            else:
                val_sig = (type(v).__name__, v)
                
            if val_sig in seen_values:
                keys_to_drop.append(k)
            else:
                seen_values[val_sig] = k
                
        for k in keys_to_drop:
            del obj[k]
            
        return obj
        
    elif isinstance(obj, list):
        return [dedup_sibling_values(item) for item in obj]
    else:
        return obj

def is_simple_dict(d):
    """Checks if a dictionary contains only primitive values (no nested lists/dicts)."""
    return isinstance(d, dict) and all(not isinstance(v, (dict, list)) for v in d.values())

def traverse_json(obj):
    """Recursively traverses the cleaned JSON and formats it into dense text lines."""
    lines = []
    
    if isinstance(obj, dict):
        simple_parts = []
        complex_items = []
        
        for k, v in obj.items():
            key_str = humanize(k)
            
            # 1. Simple dictionary -> Inline it
            if is_simple_dict(v):
                inner = ", ".join(f"{humanize(ik)}: {format_scalar(iv)}" for ik, iv in v.items())
                simple_parts.append(f"{key_str}: {inner}")
                
            # 2. Grouped List of dicts -> Inline it
            elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                first_keys = list(v[0].keys())
                all_same_keys = all(list(x.keys()) == first_keys for x in v)
                all_simple_vals = all(not isinstance(val, (dict, list)) for x in v for val in x.values())
                
                if all_same_keys and all_simple_vals:
                    header = ", ".join(humanize(k) for k in first_keys)
                    vals = "; ".join(", ".join(format_scalar(item.get(k)) for k in first_keys) for item in v)
                    simple_parts.append(f"{key_str} ({header}): {vals}")
                else:
                    complex_items.append((k, v))
                    
            # 3. Grouped List of lists -> Inline it
            elif isinstance(v, list) and v and all(isinstance(x, list) for x in v) and all(x for x in v):
                first_len = len(v[0])
                all_same_len = all(len(x) == first_len for x in v)
                all_simple_vals = all(not isinstance(val, (dict, list)) for x in v for val in x)
                
                if all_same_len and all_simple_vals:
                    vals = "; ".join(", ".join(format_scalar(x) for x in item) for item in v)
                    simple_parts.append(f"{key_str}: {vals}")
                else:
                    complex_items.append((k, v))
                    
            # 4. Simple List of primitives
            elif isinstance(v, list) and all(not isinstance(x, (dict, list)) for x in v):
                vals = ", ".join(format_scalar(x) for x in v)
                simple_parts.append(f"{key_str}: {vals}")
                
            # 5. Complex dict/list
            elif isinstance(v, (dict, list)):
                complex_items.append((k, v))
                
            # 6. Primitive
            else:
                simple_parts.append(f"{key_str}: {format_scalar(v)}")
        
        # Output all simple parts on a single line separated by semicolons
        if simple_parts:
            lines.append("; ".join(simple_parts))
            
        # Output complex items in nested blocks (no indentation)
        for k, v in complex_items:
            key_str = humanize(k)
            lines.append(f"{key_str}:")
            lines.extend(traverse_json(v))
            
    elif isinstance(obj, list):
        # This handles lists that are determined to be complex (not grouped)
        for i, item in enumerate(obj):
            if isinstance(item, dict) and is_simple_dict(item):
                parts = ", ".join(f"{humanize(k)}: {format_scalar(v)}" for k, v in item.items())
                lines.append(f"- {parts}")
            elif isinstance(item, dict):
                header = f"Item {i + 1}"
                if 'name' in item: header = format_scalar(item['name'])
                elif 'title' in item: header = format_scalar(item['title'])
                elif 'platform' in item: header = format_scalar(item['platform'])
                elif 'condition' in item: header = format_scalar(item['condition'])
                elif 'topic' in item: header = format_scalar(item['topic'])
                elif 'org' in item: header = format_scalar(item['org'])
                
                simple_parts = []
                complex_items = []
                for ik, iv in item.items():
                    if is_simple_dict(iv):
                        inner = ", ".join(f"{humanize(k)}: {format_scalar(v)}" for k, v in iv.items())
                        simple_parts.append(f"{humanize(ik)}: {inner}")
                    elif isinstance(iv, list) and all(not isinstance(x, (dict, list)) for x in iv):
                        vals = ", ".join(format_scalar(x) for x in iv)
                        simple_parts.append(f"{humanize(ik)}: {vals}")
                    elif isinstance(iv, (dict, list)):
                        complex_items.append((ik, iv))
                    else:
                        simple_parts.append(f"{humanize(ik)}: {format_scalar(iv)}")
                        
                if simple_parts:
                    lines.append(f"- {header} ({'; '.join(simple_parts)})")
                else:
                    lines.append(f"- {header}:")
                    
                for ik, iv in complex_items:
                    lines.append(f"{humanize(ik)}:")
                    lines.extend(traverse_json(iv))
            elif isinstance(item, list):
                lines.append("- [Nested List]:")
                lines.extend(traverse_json(item))
            else:
                lines.append(f"- {format_scalar(item)}")
                
    return lines

def convert_json_to_text(data):
    """Entry point to convert the loaded JSON dictionary into text."""
    # Step 1: Remove explicitly blacklisted keys (including 'brandMatch')
    data = remove_blacklisted_keys(data)
    
    # Step 2: Prune all empty/null/zero values
    cleaned_data = prune_empty_and_zero(data)
    
    # Step 3: Deduplicate identical objects/lists specifically inside the 'athlete' section
    if isinstance(cleaned_data, dict) and 'data' in cleaned_data:
        if isinstance(cleaned_data['data'], dict) and 'athlete' in cleaned_data['data']:
            athlete_section = cleaned_data['data']['athlete']
            seen_hashes = set()
            cleaned_data['data']['athlete'] = deduplicate_subtrees(athlete_section, seen_hashes)
            
    # Step 4: Deduplicate sibling values (Same value -> keep only one)
    cleaned_data = dedup_sibling_values(cleaned_data)
    
    # Step 5: Prune empty values one last time
    cleaned_data = prune_empty_and_zero(cleaned_data)
    
    # Step 6: Convert to dense text (no leading spaces)
    lines = traverse_json(cleaned_data)
    return '\n'.join(lines)
