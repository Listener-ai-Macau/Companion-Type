"""Candidate UI contract; exact native/source identity is checked separately."""
import re

def grouped_meeting_candidate(version):
    match=re.fullmatch(r'0\.1\.(0|[1-9][0-9]*)',version) if isinstance(version,str) else None
    return match is not None and int(match[1])>=79
