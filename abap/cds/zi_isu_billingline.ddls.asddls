@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'IS-U mock: billing document lines'
define view entity ZI_ISU_BillingLine
  as select from zisu_dberchz
{
  key belnr     as BillingDocument,
  key belzeile  as LineNumber,
      line_type as LineType,
      ab        as ValidFrom,
      bis       as ValidTo,
      quantity  as Quantity,
      unit      as Unit,
      price     as Price,
      @Semantics.amount.currencyCode: 'Currency'
      amount    as Amount,
      waers     as Currency
}
