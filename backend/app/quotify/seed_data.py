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
        note="Nhóm phụ gia, acid amin, enzyme và khoáng vi lượng.",
    ),
    MaterialTypeSeed(
        code="BAO_BI",
        name="Bao bì",
        note="Nhóm bao bì.",
    ),
    MaterialTypeSeed(
        code="PREMIX",
        name="Premix",
        note="Nhóm premix.",
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


@dataclass(slots=True, frozen=True)
class SupplierSeed:
    code: str
    name: str
    supplier_type: str
    status: str
    note: str
    material_codes: list[str]


@dataclass(slots=True, frozen=True)
class QuotifyUserSeed:
    full_name: str
    email: str
    password: str
    legacy_emails: tuple[str, ...] = ()


SUPPLIER_SEEDS: tuple[SupplierSeed, ...] = (
    SupplierSeed(
        code="TAN_LONG",
        name="Tập đoàn Tân Long (Tan Long Group)",
        supplier_type="domestic",
        status="active",
        note="Nhà nhập khẩu và phân phối nông sản lớn tại Việt Nam.",
        material_codes=["CORN", "SOYBEAN_MEAL", "WHEAT", "CASSAVA_CHIP", "DDGS"],
    ),
    SupplierSeed(
        code="CARGILL",
        name="Cargill Việt Nam (Cargill Vietnam)",
        supplier_type="international",
        status="active",
        note="Tập đoàn đa quốc gia hàng đầu về nông nghiệp và dinh dưỡng vật nuôi.",
        material_codes=["CORN", "SOYBEAN_MEAL", "WHEAT", "DDGS", "FISH_MEAL", "MEAT_BONE_MEAL"],
    ),
    SupplierSeed(
        code="WILMAR",
        name="Wilmar Agro Việt Nam (Wilmar Agro)",
        supplier_type="domestic",
        status="active",
        note="Nhà sản xuất và cung cấp dầu cọ, dầu nành và khô nành.",
        material_codes=["SOYBEAN_MEAL", "SOYBEAN_OIL", "PALM_OIL", "RICE_BRAN"],
    ),
    SupplierSeed(
        code="AJINOMOTO",
        name="Ajinomoto Việt Nam (Ajinomoto Vietnam)",
        supplier_type="domestic",
        status="active",
        note="Nhà sản xuất axit amin chất lượng cao dùng trong TACN.",
        material_codes=["LYSINE_HCL", "L_THREONINE"],
    ),
    SupplierSeed(
        code="CJ_VINA",
        name="CJ Vina Agri (CJ CheilJedang)",
        supplier_type="international",
        status="active",
        note="Tập đoàn Hàn Quốc chuyên cung cấp axit amin và thức ăn dinh dưỡng.",
        material_codes=["LYSINE_HCL", "DL_METHIONINE", "L_THREONINE", "L_TRYPTOPHAN", "CORN" "SOYBEAN_MEAL"],
    ),
    SupplierSeed(
        code="TIEN_THANH",
        name="Công ty TNHH Tiến Thành (Tien Thanh Co)",
        supplier_type="domestic",
        status="active",
        note="Nhà phân phối phụ gia, enzyme và premix uy tín tại thị trường VN.",
        material_codes=[
            "CHOLINE_CHLORIDE",
            "VITAMIN_PREMIX",
            "MINERAL_PREMIX",
            "PHYTASE",
            "TOXIN_BINDER",
            "MOLD_INHIBITOR",
            "ANTIOXIDANT",
            "ACIDIFIER",
        ],
    ),
    SupplierSeed(
        code="DUC_GIANG",
        name="Hóa chất Đức Giang (Duc Giang Chemicals)",
        supplier_type="domestic",
        status="active",
        note="Nhà sản xuất bột đá, DCP, MCP và hóa chất phụ gia khoáng chất lượng cao.",
        material_codes=["LIMESTONE", "DCP", "MCP", "SALT"],
    ),
    SupplierSeed(
        code="BUNGE",
        name="Bunge Asia (Bunge Limited)",
        supplier_type="international",
        status="active",
        note=(
            "Tập đoàn thương mại nông nghiệp lớn của Mỹ, "
            "chuyên chào giá USD cho ngô, khô đậu nành."
        ),
        material_codes=["CORN", "SOYBEAN_MEAL", "WHEAT"],
    ),
    SupplierSeed(
        code="LDC",
        name="Louis Dreyfus Company (LDC Asia)",
        supplier_type="international",
        status="active",
        note="Tập đoàn nông sản hàng đầu thế giới của Pháp, chuyên chào giá CIF/CFR bằng USD.",
        material_codes=["CORN", "SOYBEAN_MEAL", "WHEAT", "SOYBEAN_OIL"],
    ),
    SupplierSeed(
        code="ADM",
        name="Archer Daniels Midland (ADM Asia)",
        supplier_type="international",
        status="active",
        note=(
            "Tập đoàn dinh dưỡng vật nuôi và nông nghiệp toàn cầu, "
            "chào giá nguyên liệu thô bằng USD."
        ),
        material_codes=["CORN", "SOYBEAN_MEAL", "DDGS", "VITAMIN_PREMIX"],
    ),
    SupplierSeed(
        code="EVONIK",
        name="Evonik Industries AG",
        supplier_type="international",
        status="active",
        note=(
            "Tập đoàn hóa chất chuyên dụng của Đức, "
            "nhà cung cấp axit amin DL-Methionine chào giá USD."
        ),
        material_codes=["DL_METHIONINE", "L_THREONINE", "L_TRYPTOPHAN"],
    ),
    SupplierSeed(
        code="ENERFO",
        name="Enerfo",
        supplier_type="international",
        status="active",
        note="Nhà cung cấp ngô hạt.",
        material_codes=["CORN", "SOYBEAN_MEAL"],
    ),
    SupplierSeed(
        code="GRAINLAND",
        name="Grainland",
        supplier_type="international",
        status="active",
        note="Nhà cung cấp ngô hạt.",
        material_codes=["CORN", "SOYBEAN_MEAL"],
    ),
    SupplierSeed(
        code="ABC",
        name="ABC",
        supplier_type="domestic",
        status="active",
        note="Nhà cung cấp ngô hạt.",
        material_codes=["CORN", "SOYBEAN_MEAL"],
    ),
)


QUOTIFY_USER_SEEDS: tuple[QuotifyUserSeed, ...] = (
    QuotifyUserSeed(
        full_name="Phạm Thị Trang",
        email="phamthitrang@honghafeed.com.vn",
        password="Hongha@123",
        legacy_emails=("phamthitrang@honghafeed.com",),
    ),
    QuotifyUserSeed(
        full_name="Lê Thị Hồng",
        email="lethihong@honghafeed.com.vn",
        password="Hongha@123",
    ),
    QuotifyUserSeed(
        full_name="Vũ Hoàng Giang",
        email="vuhoanggiang@longhaigroup.com.vn",
        password="Hongha@123",
    ),
    QuotifyUserSeed(
        full_name="Nguyễn Thị Kim Loan",
        email="nguyenthikimloan@honghafeed.com.vn",
        password="Hongha@123",
    ),
    QuotifyUserSeed(
        full_name="Nguyễn Xuân Hảo",
        email="nguyenxuanhao@honghafeed.com.vn",
        password="Hongha@123",
    ),
    QuotifyUserSeed(
        full_name="Hoàng Thúy Dung",
        email="hoangthuydung@honghafeed.com.vn",
        password="Hongha@123",
    ),
    QuotifyUserSeed(
        full_name="Trịnh Thị Điểm",
        email="trinhthidiem@honghafeed.com.vn",
        password="Hongha@123",
    ),
)
