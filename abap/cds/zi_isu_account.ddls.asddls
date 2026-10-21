@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'IS-U mock: contract account overview'
define view entity ZI_ISU_Account
  as select from zisu_fkkvkp as k
    inner join   zisu_but000 as b on b.partner = k.partner
    inner join   zisu_ever   as v on v.vkont   = k.vkont
    inner join   zisu_eanl   as a on a.anlage  = v.anlage
{
  key k.vkont     as ContractAccount,
      b.partner   as BusinessPartner,
      b.name      as PartnerName,
      b.city      as City,
      v.vertrag   as Contract,
      v.einzdat   as MoveInDate,
      a.anlage    as Installation,
      a.vstelle   as Premise,
      a.tariftyp  as RateCategory,
      a.sparte    as Division
}
