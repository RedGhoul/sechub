-- The issuer's own CIK, when a filing names it (Form 3/4/5). Lets us join a
-- security back to the company's filer entity exactly, instead of by name.

ALTER TABLE security ADD COLUMN issuer_cik VARCHAR(10);
CREATE INDEX ix_security_issuer_cik ON security (issuer_cik);
