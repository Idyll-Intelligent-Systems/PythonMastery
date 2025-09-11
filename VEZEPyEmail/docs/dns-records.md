# DNS Records for vezeuniqverse.com (examples)

- MX: `vezeuniqverse.com.  3600  MX 10  mx1.vezeuniqverse.com.`
- A/AAAA: `mx1.vezeuniqverse.com. -> <your.public.ip>`
- SPF (TXT): `v=spf1 mx -all`
- DKIM (TXT at `veze._domainkey.vezeuniqverse.com`): `v=DKIM1; k=rsa; p=<public-key>`
- DMARC (TXT at `_dmarc.vezeuniqverse.com`): `v=DMARC1; p=quarantine; rua=mailto:dmarc@vezeuniqverse.com; adkim=s; aspf=s`
