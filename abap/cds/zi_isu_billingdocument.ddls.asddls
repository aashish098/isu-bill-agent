@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'IS-U mock: billing document header'
define view entity ZI_ISU_BillingDocument
  as select from zisu_erch as e
    inner join   zisu_ever as v on v.vertrag = e.vertrag
{
  key e.belnr        as BillingDocument,
      v.vkont        as ContractAccount,
      e.vertrag      as Contract,
      e.abrdats      as PeriodStart,
      e.abrdate      as PeriodEnd,
      e.kwh          as ConsumptionKwh,
      @Semantics.amount.currencyCode: 'Currency'
      e.net_amount   as NetAmount,
      @Semantics.amount.currencyCode: 'Currency'
      e.vat_amount   as VatAmount,
      @Semantics.amount.currencyCode: 'Currency'
      e.gross_amount as GrossAmount,
      e.waers        as Currency,
      e.stokz        as ReversalIndicator,
      e.reversed_by  as ReversedBy,
      e.created_on   as CreatedOn
}
