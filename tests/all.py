# -*- coding: utf-8 -*-

if __name__ == "__main__":
    from gh_org_gov.tests import run_cov_test

    run_cov_test(
        __file__,
        "gh_org_gov",
        is_folder=True,
        preview=False,
    )
