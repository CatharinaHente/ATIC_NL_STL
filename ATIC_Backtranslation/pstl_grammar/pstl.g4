grammar pstl;

@header {
'''
 Derived from PyTeLo's stl.g4 (Cristian Ioan Vasile, Lehigh University; see PyTeLo's license.txt).
 Extensions: past-time operators, symbolic bounds, bare/parametrised atoms, indexed AND/OR.
'''
}

stlProperty:
         '(' child=stlProperty ')' #parprop
    |    booleanExpr #booleanPred
    |    op=NOT child=stlProperty #formula
    |    op=BIGOP child=stlProperty #formula
    |    op=EVENT  '[' low=bound ',' high=bound ']' child=stlProperty #formula
    |    op=ALWAYS '[' low=bound ',' high=bound ']' child=stlProperty #formula
    |    op=ONCE   '[' low=bound ',' high=bound ']' child=stlProperty #formula
    |    op=HIST   '[' low=bound ',' high=bound ']' child=stlProperty #formula
    |    left=stlProperty op=IMPLIES right=stlProperty #formula
    |    left=stlProperty op=AND right=stlProperty #formula
    |    left=stlProperty op=OR right=stlProperty #formula
    |    left=stlProperty op=UNTIL '[' low=bound ',' high=bound ']' right=stlProperty #formula
    |    left=stlProperty op=SINCE '[' low=bound ',' high=bound ']' right=stlProperty #formula
    ;
bound:
         RATIONAL
    |    VARIABLE
    ;
expr:
        ( '-(' | '(' ) expr ')'
    |   <assoc=right>   expr '^' expr
    |   VARIABLE '(' expr ( ',' expr )* ')'
    |   expr ( '*' | '/' ) expr
    |   expr ( '+' | '-' ) expr
    |   RATIONAL
    |   VARIABLE
    ;
booleanExpr:
         left=expr op=( '<' | '<=' | '=' | '>=' | '>' ) right=expr
    |    op=BOOLEAN
    |    atom=VARIABLE ( '(' expr ( ',' expr )* ')' )?
    ;
AND : '&' | '&&' | '/\\' ;
OR : '|' | '||' | '\\/' ;
IMPLIES : '=>' ;
NOT : '!' | '~' ;
EVENT : 'F' | '<>' ;
ALWAYS : 'G' | '[]' ;
UNTIL : 'U' ;
ONCE : 'ONCE' ;
HIST : 'HIST' ;
SINCE : 'SINCE' ;
BIGOP : ( 'AND_' | 'OR_' ) ( [A-Za-z0-9]+ | '{' ~[}]* '}' ) ;
BOOLEAN : 'true' | 'True' | 'false' | 'False' ;
VARIABLE : ( [a-z] | [A-Z] )( [a-z] | [A-Z] | [0-9] | '_' )* ;
RATIONAL : ('-')? [0-9]* ('.')? [0-9]+ ( 'E' | 'E-' )? [0-9]* ;
WS : ( ' ' | '\t' | '\r' | '\n' )+ -> skip ;