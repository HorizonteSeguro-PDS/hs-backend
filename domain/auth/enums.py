from enum import Enum


class Role(str, Enum):
    MASTER = "master"
    PADRAO = "padrao"
    ORGAO_DE_CONTROLE = "orgao_de_controle"
