import pycountry


def get_country_code_by_its_name(name: str) -> str:
    code = pycountry.countries.get(name=name.capitalize())

    return code.alpha_2.lower()
