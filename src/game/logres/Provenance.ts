export type DataProvenance =
  | 'extracted'
  | 'confirmed'
  | 'inferred'
  | 'reconstructed'
  | 'original'

export interface ProvenanceInfo {
  provenance: DataProvenance
  source?: string
  notes?: string
}
