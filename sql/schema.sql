-- Structure de la base de données (le "plan" des tableaux).
-- "IF NOT EXISTS" : on peut relancer ce script sans erreur, il ne recrée
-- pas une table qui existe déjà.

-- Les comptes bancaires : un IBAN appartient à UNE banque dans UN pays.
CREATE TABLE IF NOT EXISTS comptes (
    iban    VARCHAR(34)  PRIMARY KEY,      -- un IBAN fait au maximum 34 caractères
    pays    CHAR(2)      NOT NULL,         -- code pays : FR, DE, ES...
    banque  VARCHAR(100) NOT NULL
);

-- Chaque transaction, avec son flag.
-- Les deux IBAN "pointent" vers la table comptes (clés étrangères) :
-- impossible d'enregistrer une transaction vers un compte inconnu.
CREATE TABLE IF NOT EXISTS transactions (
    id                    SERIAL        PRIMARY KEY,   -- numéro automatique
    datetime_transaction  TIMESTAMP     NOT NULL,
    iban_origine          VARCHAR(34)   NOT NULL REFERENCES comptes(iban),
    iban_destinataire     VARCHAR(34)   NOT NULL REFERENCES comptes(iban),
    montant               NUMERIC(12,2) NOT NULL CHECK (montant > 0),
    flag                  BOOLEAN       NOT NULL
);

-- Résultats des calculs (un total par compte ou par banque).
CREATE TABLE IF NOT EXISTS somme_envoyee_par_iban (
    iban   VARCHAR(34)   PRIMARY KEY REFERENCES comptes(iban),
    total  NUMERIC(14,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS somme_recue_par_iban (
    iban   VARCHAR(34)   PRIMARY KEY REFERENCES comptes(iban),
    total  NUMERIC(14,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS somme_envoyee_par_banque (
    banque VARCHAR(100)  PRIMARY KEY,
    total  NUMERIC(14,2) NOT NULL
);