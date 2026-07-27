from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class MaterialTypeSeed:
    code: str
    name: str
    note: str


@dataclass(slots=True, frozen=True)
class MaterialSeed:
    code: str
    name: str
    material_type_code: str
    note: str


MATERIAL_TYPE_SEEDS: tuple[MaterialTypeSeed, ...] = (
    MaterialTypeSeed(
        code="NGUYEN_LIEU",
        name="Nguyên liệu",
        note="Nhóm nguyên liệu chính dùng trong công thức thức ăn chăn nuôi.",
    ),
    MaterialTypeSeed(
        code="VI_LUONG",
        name="Vi lượng",
        note="Nhóm phụ gia, premix, acid amin, enzyme và khoáng vi lượng.",
    ),
)


MATERIAL_SEEDS: tuple[MaterialSeed, ...] = (
    MaterialSeed(
        code="CORN",
        name="Ngô hạt",
        material_type_code="NGUYEN_LIEU",
        note="Nguyên liệu cung cấp năng lượng phổ biến.",
    ),
    MaterialSeed(
        code="SOYBEAN_MEAL",
        name="Khô dầu đậu nành",
        material_type_code="NGUYEN_LIEU",
        note="Nguồn đạm thực vật phổ biến.",
    ),
    MaterialSeed(
        code="RICE_BRAN",
        name="Cám gạo",
        material_type_code="NGUYEN_LIEU",
        note="Phụ phẩm xay xát dùng trong công thức thức ăn.",
    ),
    MaterialSeed(
        code="WHEAT",
        name="Lúa mì",
        material_type_code="NGUYEN_LIEU",
        note="Nguyên liệu cung cấp năng lượng và tinh bột.",
    ),
    MaterialSeed(
        code="WHEAT_BRAN",
        name="Cám mì",
        material_type_code="NGUYEN_LIEU",
        note="Phụ phẩm từ chế biến lúa mì.",
    ),
    MaterialSeed(
        code="CASSAVA_CHIP",
        name="Sắn lát",
        material_type_code="NGUYEN_LIEU",
        note="Nguyên liệu giàu tinh bột.",
    ),
    MaterialSeed(
        code="DDGS",
        name="DDGS",
        material_type_code="NGUYEN_LIEU",
        note="Bã ngô lên men dùng làm nguồn đạm và năng lượng.",
    ),
    MaterialSeed(
        code="FISH_MEAL",
        name="Bột cá",
        material_type_code="NGUYEN_LIEU",
        note="Nguồn đạm động vật.",
    ),
    MaterialSeed(
        code="MEAT_BONE_MEAL",
        name="Bột thịt xương",
        material_type_code="NGUYEN_LIEU",
        note="Nguồn đạm và khoáng từ phụ phẩm động vật.",
    ),
    MaterialSeed(
        code="SOYBEAN_OIL",
        name="Dầu đậu nành",
        material_type_code="NGUYEN_LIEU",
        note="Nguồn chất béo bổ sung năng lượng.",
    ),
    MaterialSeed(
        code="PALM_OIL",
        name="Dầu cọ",
        material_type_code="NGUYEN_LIEU",
        note="Nguồn chất béo thực vật.",
    ),
    MaterialSeed(
        code="LIMESTONE",
        name="Bột đá",
        material_type_code="NGUYEN_LIEU",
        note="Nguồn canxi phổ biến.",
    ),
    MaterialSeed(
        code="DCP",
        name="DCP",
        material_type_code="NGUYEN_LIEU",
        note="Dicalcium phosphate, nguồn canxi và phốt pho.",
    ),
    MaterialSeed(
        code="MCP",
        name="MCP",
        material_type_code="NGUYEN_LIEU",
        note="Monocalcium phosphate, nguồn canxi và phốt pho.",
    ),
    MaterialSeed(
        code="SALT",
        name="Muối",
        material_type_code="NGUYEN_LIEU",
        note="Nguồn natri và clo.",
    ),
    MaterialSeed(
        code="LYSINE_HCL",
        name="Lysine HCl",
        material_type_code="VI_LUONG",
        note="Acid amin tổng hợp.",
    ),
    MaterialSeed(
        code="DL_METHIONINE",
        name="DL-Methionine",
        material_type_code="VI_LUONG",
        note="Acid amin tổng hợp.",
    ),
    MaterialSeed(
        code="L_THREONINE",
        name="L-Threonine",
        material_type_code="VI_LUONG",
        note="Acid amin tổng hợp.",
    ),
    MaterialSeed(
        code="L_TRYPTOPHAN",
        name="L-Tryptophan",
        material_type_code="VI_LUONG",
        note="Acid amin tổng hợp.",
    ),
    MaterialSeed(
        code="CHOLINE_CHLORIDE",
        name="Choline chloride",
        material_type_code="VI_LUONG",
        note="Phụ gia bổ sung choline.",
    ),
    MaterialSeed(
        code="VITAMIN_PREMIX",
        name="Premix vitamin",
        material_type_code="VI_LUONG",
        note="Hỗn hợp vitamin dùng trong công thức thức ăn.",
    ),
    MaterialSeed(
        code="MINERAL_PREMIX",
        name="Premix khoáng",
        material_type_code="VI_LUONG",
        note="Hỗn hợp khoáng vi lượng dùng trong công thức thức ăn.",
    ),
    MaterialSeed(
        code="PHYTASE",
        name="Enzyme phytase",
        material_type_code="VI_LUONG",
        note="Enzyme hỗ trợ sử dụng phốt pho.",
    ),
    MaterialSeed(
        code="TOXIN_BINDER",
        name="Chất hấp phụ độc tố",
        material_type_code="VI_LUONG",
        note="Phụ gia hỗ trợ kiểm soát độc tố nấm mốc.",
    ),
    MaterialSeed(
        code="MOLD_INHIBITOR",
        name="Chất chống mốc",
        material_type_code="VI_LUONG",
        note="Phụ gia hỗ trợ bảo quản nguyên liệu và thành phẩm.",
    ),
    MaterialSeed(
        code="ANTIOXIDANT",
        name="Chất chống oxy hóa",
        material_type_code="VI_LUONG",
        note="Phụ gia hạn chế oxy hóa dầu mỡ và dưỡng chất.",
    ),
    MaterialSeed(
        code="ACIDIFIER",
        name="Chất acid hóa",
        material_type_code="VI_LUONG",
        note="Phụ gia acid hữu cơ hoặc hỗn hợp acid.",
    ),
)
