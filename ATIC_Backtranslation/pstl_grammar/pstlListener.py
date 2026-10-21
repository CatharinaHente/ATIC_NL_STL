# Generated from pstl.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .pstlParser import pstlParser
else:
    from pstlParser import pstlParser

'''
 Derived from PyTeLo's stl.g4 (Cristian Ioan Vasile, Lehigh University; see PyTeLo's license.txt).
 Extensions: past-time operators, symbolic bounds, bare/parametrised atoms, indexed AND/OR.
'''


# This class defines a complete listener for a parse tree produced by pstlParser.
class pstlListener(ParseTreeListener):

    # Enter a parse tree produced by pstlParser#booleanPred.
    def enterBooleanPred(self, ctx:pstlParser.BooleanPredContext):
        pass

    # Exit a parse tree produced by pstlParser#booleanPred.
    def exitBooleanPred(self, ctx:pstlParser.BooleanPredContext):
        pass


    # Enter a parse tree produced by pstlParser#formula.
    def enterFormula(self, ctx:pstlParser.FormulaContext):
        pass

    # Exit a parse tree produced by pstlParser#formula.
    def exitFormula(self, ctx:pstlParser.FormulaContext):
        pass


    # Enter a parse tree produced by pstlParser#parprop.
    def enterParprop(self, ctx:pstlParser.ParpropContext):
        pass

    # Exit a parse tree produced by pstlParser#parprop.
    def exitParprop(self, ctx:pstlParser.ParpropContext):
        pass


    # Enter a parse tree produced by pstlParser#bound.
    def enterBound(self, ctx:pstlParser.BoundContext):
        pass

    # Exit a parse tree produced by pstlParser#bound.
    def exitBound(self, ctx:pstlParser.BoundContext):
        pass


    # Enter a parse tree produced by pstlParser#expr.
    def enterExpr(self, ctx:pstlParser.ExprContext):
        pass

    # Exit a parse tree produced by pstlParser#expr.
    def exitExpr(self, ctx:pstlParser.ExprContext):
        pass


    # Enter a parse tree produced by pstlParser#booleanExpr.
    def enterBooleanExpr(self, ctx:pstlParser.BooleanExprContext):
        pass

    # Exit a parse tree produced by pstlParser#booleanExpr.
    def exitBooleanExpr(self, ctx:pstlParser.BooleanExprContext):
        pass



del pstlParser