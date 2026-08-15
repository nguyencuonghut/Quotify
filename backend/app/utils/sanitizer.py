import html
import re

import nh3


def clean_html_to_text(text: str | None) -> str | None:
    if not text:
        return text
    text = re.sub(r"</?(p|br|div|li)[^>]*>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return " ".join(text.split())


def sanitize_html(raw_html: str) -> str:
    if raw_html is None:
        return ""
        
    # Limit payload size to 20 KB (20,480 characters)
    if len(raw_html) > 20480:
        raise ValueError("Payload size exceeds maximum allowed limit")
        
    allowed_tags = {"p", "br", "b", "strong", "i", "em", "ul", "ol", "li", "a"}
    allowed_attributes = {
        "a": {"href", "target"}
    }
    allowed_schemes = {"http", "https", "mailto"}
    
    cleaned = nh3.clean(
        raw_html,
        tags=allowed_tags,
        attributes=allowed_attributes,
        url_schemes=allowed_schemes,
        link_rel="noopener noreferrer"
    )
    
    return cleaned
