import type {
  MaterialDomain,
  MaterialDto,
  MaterialListDomain,
  MaterialListDto,
  MaterialTypeDomain,
  MaterialTypeDto,
  MaterialTypeListDomain,
  MaterialTypeListDto,
} from '@/types/materials'

export function mapMaterialTypeDtoToDomain(
  dto: MaterialTypeDto,
): MaterialTypeDomain {
  return {
    id: dto.id,
    code: dto.code,
    name: dto.name,
    status: dto.status,
    note: dto.note,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

export function mapMaterialTypeListDtoToDomain(
  dto: MaterialTypeListDto,
): MaterialTypeListDomain {
  return {
    items: dto.items.map(mapMaterialTypeDtoToDomain),
    total: dto.total,
  }
}

export function mapMaterialDtoToDomain(dto: MaterialDto): MaterialDomain {
  return {
    id: dto.id,
    code: dto.code,
    name: dto.name,
    materialTypeId: dto.material_type_id,
    materialTypeCode: dto.material_type_code,
    materialTypeName: dto.material_type_name,
    status: dto.status,
    note: dto.note,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

export function mapMaterialListDtoToDomain(
  dto: MaterialListDto,
): MaterialListDomain {
  return {
    items: dto.items.map(mapMaterialDtoToDomain),
    total: dto.total,
  }
}
