# -*- coding: utf-8 -*-

import dataclasses
from which_runtime.api import runtime


@dataclasses.dataclass
class Config:
    github_token: str
    github_org_name: str

    @classmethod
    def load(cls):
        if runtime.is_ci_runtime_group:
            raise RuntimeError
        else:
            from home_secret_toml.api import hs

            return cls(
                github_token=hs.v("github.accounts.esc.users.sh_esc.secrets.dev.value"),
                github_org_name="easyscale-academy",
            )
