"""Standard numbered folder structures created for a new project, matching common
animation/post-production studio conventions. Applying a template only creates
folders that don't already exist - it never touches or deletes existing content.
"""

FOLDER_TEMPLATES = {
    "Vídeo": [
        "00_Admin",
        "01_Preproduccion",
        "02_Rodaje",
        "03_Material_Bruto",
        "04_Edicion",
        "05_Sonido",
        "06_Color",
        "07_Entregas",
    ],
    "Animación": [
        "00_Admin",
        "01_Preproduccion",
        "02_Guion_Storyboard",
        "03_Diseno_Personajes",
        "04_Animatica",
        "05_Animacion",
        "06_Render",
        "07_Composicion",
        "08_Sonido",
        "09_Entregas",
    ],
    "Edición": [
        "00_Admin",
        "01_Material_Bruto",
        "02_Proyecto_Edicion",
        "03_Musica_Sonido",
        "04_Grafismos",
        "05_Color",
        "06_Entregas",
    ],
    "3D": [
        "00_Admin",
        "01_Referencias",
        "02_Modelado",
        "03_Texturizado",
        "04_Rigging",
        "05_Animacion",
        "06_Render",
        "07_Composicion",
        "08_Entregas",
    ],
    "Rodaje": [
        "00_Preproduccion",
        "01_Guion_Shotlist",
        "02_Localizaciones",
        "03_Casting",
        "04_Material_Rodaje",
        "05_Sonido_Directo",
        "06_Entregas",
    ],
    "Otro": [
        "00_Admin",
        "01_Material",
        "02_Entregas",
    ],
}


def folders_for(project_type: str) -> list[str]:
    return FOLDER_TEMPLATES.get(project_type, FOLDER_TEMPLATES["Otro"])
