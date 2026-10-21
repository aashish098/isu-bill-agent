"! Behavior pool for ZI_ISU_ClarificationCase
"! Global part (create this class in ADT; paste the local part into the "Local Types" tab)
CLASS zbp_i_isu_clarificationcase DEFINITION PUBLIC ABSTRACT FINAL
  FOR BEHAVIOR OF zi_isu_clarificationcase.
ENDCLASS.

CLASS zbp_i_isu_clarificationcase IMPLEMENTATION.
ENDCLASS.

*----------------------------------------------------------------------*
* Local Types (CCIMP)
*----------------------------------------------------------------------*
CLASS lhc_clarificationcase DEFINITION INHERITING FROM cl_abap_behavior_handler.
  PRIVATE SECTION.
    METHODS get_global_authorizations FOR GLOBAL AUTHORIZATION
      IMPORTING REQUEST requested_authorizations FOR ClarificationCase RESULT result.

    METHODS setinitialstatus FOR DETERMINE ON MODIFY
      IMPORTING keys FOR ClarificationCase~setInitialStatus.
ENDCLASS.

CLASS lhc_clarificationcase IMPLEMENTATION.

  METHOD get_global_authorizations.
    " POC: everyone may create/update. In a real system check a custom
    " authorization object here (e.g. by contract account region).
    IF requested_authorizations-%create = if_abap_behv=>mk-on.
      result-%create = if_abap_behv=>auth-allowed.
    ENDIF.
    IF requested_authorizations-%update = if_abap_behv=>mk-on.
      result-%update = if_abap_behv=>auth-allowed.
    ENDIF.
  ENDMETHOD.

  METHOD setinitialstatus.
    READ ENTITIES OF zi_isu_clarificationcase IN LOCAL MODE
      ENTITY ClarificationCase
        FIELDS ( Status ) WITH CORRESPONDING #( keys )
      RESULT DATA(cases).

    DELETE cases WHERE Status IS NOT INITIAL.
    CHECK cases IS NOT INITIAL.

    MODIFY ENTITIES OF zi_isu_clarificationcase IN LOCAL MODE
      ENTITY ClarificationCase
        UPDATE FIELDS ( Status )
        WITH VALUE #( FOR c IN cases ( %tky = c-%tky  Status = 'OPEN' ) ).
  ENDMETHOD.

ENDCLASS.
