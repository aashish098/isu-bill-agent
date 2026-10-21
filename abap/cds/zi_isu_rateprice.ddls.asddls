@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'IS-U mock: energy price per rate category'
define view entity ZI_ISU_RatePrice
  as select from zisu_rates
{
  key tariftyp     as RateCategory,
  key ab           as ValidFrom,
      bis          as ValidTo,
      energy_price as EnergyPrice
}
