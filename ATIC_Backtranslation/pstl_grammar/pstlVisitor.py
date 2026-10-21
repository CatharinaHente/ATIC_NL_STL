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


# This class defines a complete generic visitor for a parse tree produced by pstlParser.

class pstlVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by pstlParser#booleanPred.
    def visitBooleanPred(self, ctx:pstlParser.BooleanPredContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by pstlParser#formula.
    def visitFormula(self, ctx:pstlParser.FormulaContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by pstlParser#parprop.
    def visitParprop(self, ctx:pstlParser.ParpropContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by pstlParser#bound.
    def visitBound(self, ctx:pstlParser.BoundContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by pstlParser#expr.
    def visitExpr(self, ctx:pstlParser.ExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by pstlParser#booleanExpr.
    def visitBooleanExpr(self, ctx:pstlParser.BooleanExprContext):
        return self.visitChildren(ctx)



del pstlParser