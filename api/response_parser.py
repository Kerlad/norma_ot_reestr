"""
Response parser for Mintrud API.
Parses XML responses from the server.
"""
import html
import logging
import re
from typing import Dict, Any

from xml.etree.ElementTree import ParseError as _ETParseError
from defusedxml.ElementTree import fromstring as _fromstring
from defusedxml.common import DefusedXmlException

from utils.logger import mask_sensitive, filter_sensitive_text

logger = logging.getLogger(__name__)

ERROR_MAP = {
    "400": "Ошибка валидации XML. Проверьте соответствие схеме XSD",
    "401": "Ошибка авторизации. Проверьте API ключ",
    "403": "Доступ запрещён",
    "500": "Ошибка сервера Минтруда. Повторите попытку позже",
    "503": "Сервис временно недоступен. Повторите попытку позже",
}


_BR_RE = re.compile(r"<\s*/?\s*br\s*/?\s*>", re.IGNORECASE)
_BLOCK_END_RE = re.compile(r"<\s*/\s*(p|div|li)\s*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^<>]{0,200}>")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def clean_server_message(message: str) -> str:
    """Server messages may contain HTML (<i>, </br>, <strong>): convert them to plain text."""
    if not message:
        return ""
    text = _BR_RE.sub("\n", message)
    text = _BLOCK_END_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text).replace("\r\n", "\n")
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _BLANK_LINES_RE.sub("\n\n", text).strip()


def _format_error(status_code: str, message: str) -> str:
    """Format error message from status code."""
    if status_code in ERROR_MAP:
        base_msg = ERROR_MAP[status_code]
    else:
        base_msg = f"Ошибка сервера (код {status_code})"

    message = clean_server_message(message)
    if message:
        return f"{base_msg}\n\nПодробности: {message}"
    return base_msg


def _find_error(root):
    """Return the <Error> element: the root itself or nested in <Response>."""
    if root.tag == "Error":
        return root
    return root.find("Error")


def _error_text(err) -> str:
    """Build a user-facing text from an <Error> element (adds RequestId)."""
    status = err.findtext("StatusCode") or "unknown"
    msg = err.findtext("Message") or ""
    text = _format_error(status.strip(), msg.strip())
    request_id = (err.findtext("RequestId") or "").strip()
    if request_id:
        text += "\n\nКод обращения в поддержку: %s" % request_id
    return text


def _decode_response(response_bytes: bytes) -> str:
    """Decode response bytes with fallback encodings."""
    for enc in ('utf-8', 'cp1251'):
        try:
            return response_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return str(response_bytes)


def parse_send_response(response_bytes: bytes, status_code: int = 200) -> Dict[str, Any]:
    """
    Parse response from send XML API.
    
    Args:
        response_bytes: Raw response bytes
        status_code: HTTP status code
    
    Returns:
        Dict with keys: success, set_id, send_educated_person, message, error, raw_response
    """
    response_text = _decode_response(response_bytes)
    
    logger.info("Response received: %d chars", len(response_text))
    
    try:
        root = _fromstring(response_text)
    except (DefusedXmlException, _ETParseError, ValueError) as e:
        logger.error("XML parse error: %s", type(e).__name__)
        return {
            "success": False,
            "set_id": None,
            "message": None,
            "error": f"HTTP {status_code}: Не удалось разобрать ответ сервера",
            "raw_response": response_text[:1000]
        }

    err = _find_error(root)
    if err is not None:
        logger.error("Server returned an error response")
        return {
            "success": False,
            "set_id": None,
            "message": None,
            "error": _error_text(err),
            "raw_response": response_text[:1000]
        }

    if root.tag == "Response":
        set_id_elem = root.find("SetId")
        send_elem = root.find("SendEducatedPerson")
        msg_elem = root.find("Message")
        
        set_id = set_id_elem.text if set_id_elem is not None else ""
        if not (set_id or "").strip():
            return {
                "success": False,
                "set_id": None,
                "message": None,
                "error": "Сервер не вернул номер набора (SetId)",
                "raw_response": response_text[:500]
            }
        send_edu = send_elem.text if send_elem is not None else "false"
        msg = clean_server_message(msg_elem.text if msg_elem is not None else "")

        logger.info("Success: SetId=%s, SendEducatedPerson=%s", mask_sensitive(set_id), send_edu)
        
        return {
            "success": True,
            "set_id": set_id,
            "send_educated_person": send_edu.lower() == "true",
            "message": msg,
            "error": None,
            "raw_response": None
        }

    elif root.tag == "Result":
        set_id_elem = root.find("SetId")
        send_elem = root.find("SendEducatedPerson")
        msg_elem = root.find("Message")

        set_id = set_id_elem.text if set_id_elem is not None else ""
        send_edu = send_elem.text if send_elem is not None else "false"
        msg = msg_elem.text if msg_elem is not None else ""

        logger.info("Success (Result tag): SetId=%s, SendEducatedPerson=%s", mask_sensitive(set_id), send_edu)

        return {
            "success": True,
            "set_id": set_id,
            "send_educated_person": send_edu.lower() == "true",
            "message": msg,
            "error": None,
            "raw_response": None
        }

    elif root.tag == "Message":
        set_id_elem = root.find("SetId")
        send_elem = root.find("SendEducatedPerson")
        msg_elem = root.find("Text")

        set_id = set_id_elem.text if set_id_elem is not None else ""
        send_edu = send_elem.text if send_elem is not None else "false"
        msg = msg_elem.text if msg_elem is not None else ""

        logger.info("Success (Message tag): SetId=%s", mask_sensitive(set_id))

        return {
            "success": True,
            "set_id": set_id,
            "send_educated_person": send_edu.lower() == "true",
            "message": msg,
            "error": None,
            "raw_response": None
        }

    elif root.tag == "SetId":
        set_id_elem = root.find("Id")
        send_elem = root.find("SendEducatedPerson")

        set_id = set_id_elem.text if set_id_elem is not None else str(root.tag)
        send_edu = send_elem.text if send_elem is not None else "false"

        return {
            "success": True,
            "set_id": set_id,
            "send_educated_person": send_edu.lower() == "true",
            "message": None,
            "error": None,
            "raw_response": None
        }

    elif root.tag == "Error":
        status_code_elem = root.find("StatusCode")
        msg_elem = root.find("Message")
        
        status_code_str = status_code_elem.text if status_code_elem is not None else "unknown"
        msg = msg_elem.text if msg_elem is not None else ""
        
        error_msg = _format_error(status_code_str, msg)
        logger.error("Registry error: %s - %s", status_code_str, filter_sensitive_text(msg or ""))
        
        return {
            "success": False,
            "set_id": None,
            "message": None,
            "error": error_msg,
            "raw_response": response_text[:1000]
        }
    
    else:
        logger.error("Unknown response format")
        return {
            "success": False,
            "set_id": None,
            "message": None,
            "error": f"Неизвестный формат ответа: {root.tag}",
            "raw_response": response_text[:500]
        }


def parse_setid_response(response_bytes: bytes, status_code: int = 200) -> Dict[str, Any]:
    """
    Parse response from query by SetId API.

    Args:
        response_bytes: Raw response bytes
        status_code: HTTP status code

    Returns:
        Dict with keys: success, records, error, raw_response
    """
    response_text = _decode_response(response_bytes)

    logger.info("parse_setid_response: status=%s, text_len=%d", status_code, len(response_text))

    try:
        root = _fromstring(response_text)
    except (DefusedXmlException, _ETParseError, ValueError) as e:
        logger.error("XML parse error: %s", type(e).__name__)
        return {
            "success": False,
            "records": [],
            "error": f"HTTP {status_code}: Не удалось разобрать ответ",
            "raw_response": response_text[:1000]
        }

    logger.info("Root tag: %s", root.tag)

    err = _find_error(root)
    if err is not None:
        return {
            "success": False,
            "records": [],
            "error": _error_text(err),
            "raw_response": response_text[:1000]
        }

    if root.tag == "Response":
        records = []
        for person in root.findall("EducatedPerson"):
            record = {
                "snils": person.findtext("SNILS", ""),
                "reg_number": person.findtext("RegNumber", ""),
                "status": person.findtext("Status", ""),
                "message": person.findtext("Message", ""),
                "baseNo": person.findtext("RegNumber", ""),
                "LastName": person.findtext("LastName", ""),
                "FirstName": person.findtext("FirstName", ""),
                "MiddleName": person.findtext("MiddleName", ""),
                "learnProgramId": person.get("learnProgramId", ""),
                "LearnProgramTitle": person.get("learnProgramTitle", ""),
                "ProtocolNumber": person.get("ProtocolNumber", ""),
                "Date": person.get("Date", ""),
            }
            records.append(record)
        return {
            "success": True,
            "records": records,
            "error": None,
            "raw_response": None
        }

    elif root.tag == "EducatedPersons":
        records = []
        for rec in root.findall("RegistryRecord"):
            base_no = rec.get("baseNo", "")
            set_id = rec.get("setId", "")
            base_date = rec.get("baseDateCreated", "")
            internal_exam = rec.get("internalExamination", "")
            outer_id = rec.get("outerId", "")

            snils = ""
            last_name = ""
            first_name = ""
            middle_name = ""
            position = ""
            employer_inn = ""
            employer_title = ""
            program_id = ""
            program_title = ""
            protocol = ""
            date = ""
            is_passed = ""

            for child in rec:
                tag = child.tag
                if tag == "Worker":
                    snils = child.findtext("Snils", "")
                    last_name = child.findtext("LastName", "")
                    first_name = child.findtext("FirstName", "")
                    middle_name = child.findtext("MiddleName", "")
                    position = child.findtext("Position", "")
                    employer_inn = child.findtext("EmployerInn", "")
                    employer_title = child.findtext("EmployerTitle", "")
                elif tag == "EmployerOrganization":
                    if not employer_inn:
                        employer_inn = child.findtext("Inn", "")
                    if not employer_title:
                        employer_title = child.findtext("Title", "")
                elif tag == "Test":
                    program_id = child.get("learnProgramId", "")
                    is_passed = child.get("isPassed", "")
                    program_title = child.findtext("LearnProgramTitle", "")
                    protocol = child.findtext("ProtocolNumber", "")
                    date_raw = child.findtext("Date", "")
                    if date_raw:
                        date = date_raw.split()[0] if ' ' in date_raw else date_raw

            record = {
                "Snils": snils,
                "LastName": last_name,
                "FirstName": first_name,
                "MiddleName": middle_name,
                "Position": position,
                "EmployerInn": employer_inn,
                "EmployerTitle": employer_title,
                "learnProgramId": program_id,
                "LearnProgramTitle": program_title,
                "ProtocolNumber": protocol,
                "Date": date,
                "isPassed": is_passed,
                "baseNo": base_no,
                "setId": set_id,
                "baseDateCreated": base_date,
                "internalExamination": internal_exam,
                "outerId": outer_id,
            }
            records.append(record)

        return {
            "success": True,
            "records": records,
            "error": None,
            "raw_response": None
        }

    elif root.tag == "Error":
        status_code_elem = root.find("StatusCode")
        msg_elem = root.find("Message")
        
        status_code_str = status_code_elem.text if status_code_elem is not None else "unknown"
        msg = msg_elem.text if msg_elem is not None else ""
        
        return {
            "success": False,
            "records": [],
            "error": _format_error(status_code_str, msg),
            "raw_response": response_text[:1000]
        }
    
    else:
        return {
            "success": False,
            "records": [],
            "error": f"Неизвестный формат ответа: {root.tag}",
            "raw_response": response_text[:500]
        }


def parse_snils_response(response_bytes: bytes, status_code: int = 200) -> Dict[str, Any]:
    """
    Parse response from query by SNILS API.
    
    Args:
        response_bytes: Raw response bytes
        status_code: HTTP status code
    
    Returns:
        Dict with keys: success, records, error, raw_response
    """
    return parse_setid_response(response_bytes, status_code)


def parse_error_response(response_bytes: bytes) -> Dict[str, Any]:
    """
    Parse error response from any API call.
    
    Args:
        response_bytes: Raw response bytes
    
    Returns:
        Dict with keys: success, error, raw_response
    """
    response_text = _decode_response(response_bytes)
    
    try:
        root = _fromstring(response_text)
    except (DefusedXmlException, _ETParseError, ValueError) as e:
        logger.error("Error response parse failed: %s", type(e).__name__)
        return {
            "success": False,
            "error": "Не удалось разобрать ответ сервера",
            "raw_response": response_text[:1000]
        }
    
    if root.tag == "Error":
        status_code_elem = root.find("StatusCode")
        msg_elem = root.find("Message")
        
        status_code_str = status_code_elem.text if status_code_elem is not None else "unknown"
        msg = msg_elem.text if msg_elem is not None else ""
        
        return {
            "success": False,
            "error": _format_error(status_code_str, msg),
            "raw_response": response_text[:1000]
        }
    
    return {
        "success": False,
        "error": "Сервер вернул неожиданный ответ",
        "raw_response": response_text[:1000]
    }