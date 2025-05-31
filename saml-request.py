import base64
import urllib.parse
import zlib
import uuid
from datetime import datetime, timezone

def generate_saml_request(issuer, acs_url, destination):
    """
    Generate a SAML 2.0 AuthnRequest string (URL-encoded, base64-encoded, DEFLATE compressed)
    suitable for HTTP-Redirect binding.

    Args:
        issuer (str): The entity ID of the Service Provider (SP).
        acs_url (str): Assertion Consumer Service URL where the IdP should post the response.
        destination (str): The SSO endpoint URL of the Identity Provider (IdP).

    Returns:
        str: The URL-encoded SAMLRequest parameter value.
    """
    # Generate a unique ID for the request
    request_id = 'SNC' + uuid.uuid4().hex

    # Current time in UTC, formatted per SAML spec
    issue_instant = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    # Build the AuthnRequest XML
    authn_request_xml = f"""<saml2p:AuthnRequest xmlns:saml2p="urn:oasis:names:tc:SAML:2.0:protocol"
    AssertionConsumerServiceURL="{acs_url}"
    Destination="{destination}"
    ForceAuthn="false"
    ID="{request_id}"
    IsPassive="false"
    IssueInstant="{issue_instant}"
    ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
    ProviderName="{acs_url}"
    Version="2.0">
        <saml2:Issuer xmlns:saml2="urn:oasis:names:tc:SAML:2.0:assertion">{issuer}</saml2:Issuer><saml2p:NameIDPolicy AllowCreate="true" Format="urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified"/>
    </saml2p:AuthnRequest>"""

    # Compress the XML using DEFLATE (raw, -15 window bits)
    deflated = zlib.compress(authn_request_xml.encode('utf-8'))[2:-4]  # strip zlib headers and checksum

    # Base64 encode
    b64_encoded = base64.b64encode(deflated)

    # URL-encode
    url_encoded = urllib.parse.quote_plus(b64_encoded)

    return url_encoded


def decode_saml_request(saml_request_encoded):
    # URL-decode the input
    url_decoded = urllib.parse.unquote(saml_request_encoded)
    # Base64-decode
    base64_decoded = base64.b64decode(url_decoded)
    # Decompress using raw DEFLATE (-zlib.MAX_WBITS)
    xml_bytes = zlib.decompress(base64_decoded, -zlib.MAX_WBITS)
    return xml_bytes.decode('utf-8')


# Example usage:
if __name__ == "__main__":
    issuer = "https://hsbcitid.service-now.com"
    acs_url = "https://hsbcitid.service-now.com/navpage.do"
    destination = "https://login.microsoftonline.com/e0fd434d-ba64-497b-90d2-859c472e1a92/saml2"

    saml_request = generate_saml_request(issuer, acs_url, destination)
    print("SAMLRequest:", saml_request)

    decoded_saml_req = decode_saml_request(saml_request)
    print("decoded SMALRequest: ", decoded_saml_req)