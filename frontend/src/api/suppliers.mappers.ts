import type {
  SupplierContactDomain,
  SupplierContactDto,
  SupplierDomain,
  SupplierDto,
  SupplierListDomain,
  SupplierListDto,
  SupplierMaterialDomain,
  SupplierMaterialDto,
  SupplierLookupDto,
  SupplierType,
} from '@/types/suppliers'

function normalizeSupplierTypes(value: SupplierDto['supplier_type']): SupplierType[] {
  if (Array.isArray(value)) {
    return value
  }
  return [value]
}

export function mapSupplierContactDtoToDomain(
  dto: SupplierContactDto,
): SupplierContactDomain {
  return {
    id: dto.id,
    name: dto.name,
    title: dto.title,
    email: dto.email,
    phone: dto.phone,
    status: dto.status,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

export function mapSupplierMaterialDtoToDomain(
  dto: SupplierMaterialDto,
): SupplierMaterialDomain {
  return {
    materialId: dto.material_id,
    materialCode: dto.material_code,
    materialName: dto.material_name,
  }
}

export function mapSupplierDtoToDomain(dto: SupplierDto): SupplierDomain {
  return {
    id: dto.id,
    code: dto.code,
    name: dto.name,
    supplierType: normalizeSupplierTypes(dto.supplier_type),
    status: dto.status,
    taxCode: dto.tax_code,
    address: dto.address,
    note: dto.note,
    contacts: dto.contacts.map(mapSupplierContactDtoToDomain),
    materials: dto.materials.map(mapSupplierMaterialDtoToDomain),
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

export function mapSupplierListDtoToDomain(
  dto: SupplierListDto,
): SupplierListDomain {
  return {
    items: dto.items.map(mapSupplierDtoToDomain),
    total: dto.total,
  }
}

export function mapSupplierLookupDtoToDomain(dto: SupplierLookupDto): SupplierDomain[] {
  return dto.items.map(mapSupplierDtoToDomain)
}
