@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'IS-U mock: bill clarification case'
define root view entity ZI_ISU_ClarificationCase
  as select from zisu_clarif
{
  key case_uuid             as CaseUuid,
      vkont                 as ContractAccount,
      belnr                 as BillingDocument,
      category              as Category,
      summary               as Summary,
      status                as Status,
      @Semantics.user.createdBy: true
      created_by            as CreatedBy,
      @Semantics.systemDateTime.createdAt: true
      created_at            as CreatedAt,
      @Semantics.systemDateTime.localInstanceLastChangedAt: true
      local_last_changed_at as LocalLastChangedAt
}
