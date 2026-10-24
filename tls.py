"""HTTPS local do Thingmabobber: uma autoridade (CA) propria + certificado do servidor com os IPs da rede.

O celular instala a CA uma vez (perfil .mobileconfig) e passa a confiar nos certificados que ela assina.
Os certificados do servidor sao refeitos sozinhos quando os IPs do PC mudam; a CA continua a mesma,
entao o celular nao precisa instalar nada de novo. Precisa do pacote "cryptography" (pip install cryptography)."""
import datetime
import ipaddress
import os
import ssl

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    HAS_CRYPTO = True
except ImportError:   # sem o pacote o app continua em HTTP
    HAS_CRYPTO = False

CA_NAME = "Thingmabobber Local CA"
# A CA so vale para redes locais: mesmo que a chave dela vaze, nao serve para falsificar sites da internet.
LOCAL_NETS = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16", "100.64.0.0/10", "26.0.0.0/8"]   # 100.64/10 = Tailscale, 26/8 = Radmin VPN


def is_local_ip(v):
    try: ip = ipaddress.ip_address(v)
    except ValueError: return False
    return any(ip in ipaddress.ip_network(n) for n in LOCAL_NETS)


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _write_key(path, key):
    with open(path, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))


def _write_cert(path, cert):
    with open(path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


def ensure_ca(folder):
    """Cria (uma unica vez) a CA. Retorna (chave, certificado)."""
    os.makedirs(folder, exist_ok=True)
    kp, cp = os.path.join(folder, "ca.key"), os.path.join(folder, "ca.pem")
    if os.path.exists(kp) and os.path.exists(cp):
        with open(kp, "rb") as f: key = serialization.load_pem_private_key(f.read(), None)
        with open(cp, "rb") as f: cert = x509.load_pem_x509_certificate(f.read())
        if cert.not_valid_after_utc > _now() + datetime.timedelta(days=30):
            return key, cert
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, CA_NAME), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Thingmabobber")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(_now() - datetime.timedelta(days=1)).not_valid_after(_now() + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.NameConstraints(permitted_subtrees=[x509.IPAddress(ipaddress.ip_network(n)) for n in LOCAL_NETS] + [x509.DNSName("localhost")], excluded_subtrees=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .sign(key, hashes.SHA256()))
    _write_key(kp, key); _write_cert(cp, cert)
    return key, cert


def ca_der(folder):
    _, cert = ensure_ca(folder)
    return cert.public_bytes(serialization.Encoding.DER)


def ensure_server_cert(folder, ips, names=("localhost",)):
    """Certificado do servidor valido para os IPs/nomes dados. Refeito se a lista mudou ou esta perto de vencer. Retorna (cert.pem, key.pem)."""
    ca_key, ca_cert = ensure_ca(folder)
    cp, kp, sp = os.path.join(folder, "server.pem"), os.path.join(folder, "server.key"), os.path.join(folder, "server.san")
    want = sorted({v for v in list(ips) + ["127.0.0.1"] if is_local_ip(v)}) + sorted(set(names))
    if all(os.path.exists(p) for p in (cp, kp, sp)):
        with open(sp, encoding="utf-8") as f: have = f.read().split()
        with open(cp, "rb") as f: cur = x509.load_pem_x509_certificate(f.read())
        if have == want and cur.not_valid_after_utc > _now() + datetime.timedelta(days=30):
            return cp, kp
    key = ec.generate_private_key(ec.SECP256R1())
    sans = []
    for v in want:
        try: sans.append(x509.IPAddress(ipaddress.ip_address(v)))
        except ValueError: sans.append(x509.DNSName(v))
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Thingmabobber server")])).issuer_name(ca_cert.subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(_now() - datetime.timedelta(days=1)).not_valid_after(_now() + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(sans), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=False, crl_sign=False, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=True, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    _write_cert(cp, cert); _write_key(kp, key)
    with open(sp, "w", encoding="utf-8") as f: f.write("\n".join(want))
    return cp, kp


def server_context(folder, ips):
    cp, kp = ensure_server_cert(folder, ips)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cp, kp)
    return ctx
