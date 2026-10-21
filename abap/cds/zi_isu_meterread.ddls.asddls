@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'IS-U mock: meter reading results'
define view entity ZI_ISU_MeterRead
  as select from zisu_eabl  as r
    inner join   zisu_egerh as g on g.equnr  = r.equnr
    inner join   zisu_ever  as v on v.anlage = g.anlage
{
  key r.ablbelnr  as MeterReadDocument,
      v.vkont     as ContractAccount,
      r.equnr     as Device,
      g.sernr     as SerialNumber,
      g.faktor    as Factor,
      r.adat      as ReadDate,
      r.zwstand   as Reading,
      r.istablart as ReadType,     // 01 utility, 02 customer, 03 automatic estimation
      r.ablesgr   as ReadReason    // 01 periodic, 21 installation, 22 removal
}
