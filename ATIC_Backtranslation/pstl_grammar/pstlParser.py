# Generated from pstl.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO


'''
 Derived from PyTeLo's stl.g4 (Cristian Ioan Vasile, Lehigh University; see PyTeLo's license.txt).
 Extensions: past-time operators, symbolic bounds, bare/parametrised atoms, indexed AND/OR.
'''

def serializedATN():
    return [
        4,1,31,143,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,1,0,1,0,1,0,1,0,1,0,1,
        0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,
        0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,
        0,1,0,1,0,1,0,1,0,3,0,51,8,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,
        1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,
        1,0,1,0,5,0,80,8,0,10,0,12,0,83,9,0,1,1,1,1,1,2,1,2,1,2,1,2,1,2,
        1,2,1,2,1,2,1,2,1,2,5,2,97,8,2,10,2,12,2,100,9,2,1,2,1,2,1,2,1,2,
        3,2,106,8,2,1,2,1,2,1,2,1,2,1,2,1,2,1,2,1,2,1,2,5,2,117,8,2,10,2,
        12,2,120,9,2,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,5,3,132,8,3,
        10,3,12,3,135,9,3,1,3,1,3,3,3,139,8,3,3,3,141,8,3,1,3,0,2,0,4,4,
        0,2,4,6,0,5,1,0,29,30,2,0,1,1,6,6,1,0,8,9,1,0,10,11,1,0,12,16,161,
        0,50,1,0,0,0,2,84,1,0,0,0,4,105,1,0,0,0,6,140,1,0,0,0,8,9,6,0,-1,
        0,9,10,5,1,0,0,10,11,3,0,0,0,11,12,5,2,0,0,12,51,1,0,0,0,13,51,3,
        6,3,0,14,15,5,20,0,0,15,51,3,0,0,11,16,17,5,27,0,0,17,51,3,0,0,10,
        18,19,5,21,0,0,19,20,5,3,0,0,20,21,3,2,1,0,21,22,5,4,0,0,22,23,3,
        2,1,0,23,24,5,5,0,0,24,25,3,0,0,9,25,51,1,0,0,0,26,27,5,22,0,0,27,
        28,5,3,0,0,28,29,3,2,1,0,29,30,5,4,0,0,30,31,3,2,1,0,31,32,5,5,0,
        0,32,33,3,0,0,8,33,51,1,0,0,0,34,35,5,24,0,0,35,36,5,3,0,0,36,37,
        3,2,1,0,37,38,5,4,0,0,38,39,3,2,1,0,39,40,5,5,0,0,40,41,3,0,0,7,
        41,51,1,0,0,0,42,43,5,25,0,0,43,44,5,3,0,0,44,45,3,2,1,0,45,46,5,
        4,0,0,46,47,3,2,1,0,47,48,5,5,0,0,48,49,3,0,0,6,49,51,1,0,0,0,50,
        8,1,0,0,0,50,13,1,0,0,0,50,14,1,0,0,0,50,16,1,0,0,0,50,18,1,0,0,
        0,50,26,1,0,0,0,50,34,1,0,0,0,50,42,1,0,0,0,51,81,1,0,0,0,52,53,
        10,5,0,0,53,54,5,19,0,0,54,80,3,0,0,6,55,56,10,4,0,0,56,57,5,17,
        0,0,57,80,3,0,0,5,58,59,10,3,0,0,59,60,5,18,0,0,60,80,3,0,0,4,61,
        62,10,2,0,0,62,63,5,23,0,0,63,64,5,3,0,0,64,65,3,2,1,0,65,66,5,4,
        0,0,66,67,3,2,1,0,67,68,5,5,0,0,68,69,3,0,0,3,69,80,1,0,0,0,70,71,
        10,1,0,0,71,72,5,26,0,0,72,73,5,3,0,0,73,74,3,2,1,0,74,75,5,4,0,
        0,75,76,3,2,1,0,76,77,5,5,0,0,77,78,3,0,0,2,78,80,1,0,0,0,79,52,
        1,0,0,0,79,55,1,0,0,0,79,58,1,0,0,0,79,61,1,0,0,0,79,70,1,0,0,0,
        80,83,1,0,0,0,81,79,1,0,0,0,81,82,1,0,0,0,82,1,1,0,0,0,83,81,1,0,
        0,0,84,85,7,0,0,0,85,3,1,0,0,0,86,87,6,2,-1,0,87,88,7,1,0,0,88,89,
        3,4,2,0,89,90,5,2,0,0,90,106,1,0,0,0,91,92,5,29,0,0,92,93,5,1,0,
        0,93,98,3,4,2,0,94,95,5,4,0,0,95,97,3,4,2,0,96,94,1,0,0,0,97,100,
        1,0,0,0,98,96,1,0,0,0,98,99,1,0,0,0,99,101,1,0,0,0,100,98,1,0,0,
        0,101,102,5,2,0,0,102,106,1,0,0,0,103,106,5,30,0,0,104,106,5,29,
        0,0,105,86,1,0,0,0,105,91,1,0,0,0,105,103,1,0,0,0,105,104,1,0,0,
        0,106,118,1,0,0,0,107,108,10,6,0,0,108,109,5,7,0,0,109,117,3,4,2,
        6,110,111,10,4,0,0,111,112,7,2,0,0,112,117,3,4,2,5,113,114,10,3,
        0,0,114,115,7,3,0,0,115,117,3,4,2,4,116,107,1,0,0,0,116,110,1,0,
        0,0,116,113,1,0,0,0,117,120,1,0,0,0,118,116,1,0,0,0,118,119,1,0,
        0,0,119,5,1,0,0,0,120,118,1,0,0,0,121,122,3,4,2,0,122,123,7,4,0,
        0,123,124,3,4,2,0,124,141,1,0,0,0,125,141,5,28,0,0,126,138,5,29,
        0,0,127,128,5,1,0,0,128,133,3,4,2,0,129,130,5,4,0,0,130,132,3,4,
        2,0,131,129,1,0,0,0,132,135,1,0,0,0,133,131,1,0,0,0,133,134,1,0,
        0,0,134,136,1,0,0,0,135,133,1,0,0,0,136,137,5,2,0,0,137,139,1,0,
        0,0,138,127,1,0,0,0,138,139,1,0,0,0,139,141,1,0,0,0,140,121,1,0,
        0,0,140,125,1,0,0,0,140,126,1,0,0,0,141,7,1,0,0,0,10,50,79,81,98,
        105,116,118,133,138,140
    ]

class pstlParser ( Parser ):

    grammarFileName = "pstl.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'('", "')'", "'['", "','", "']'", "'-('", 
                     "'^'", "'*'", "'/'", "'+'", "'-'", "'<'", "'<='", "'='", 
                     "'>='", "'>'", "<INVALID>", "<INVALID>", "'=>'", "<INVALID>", 
                     "<INVALID>", "<INVALID>", "'U'", "'ONCE'", "'HIST'", 
                     "'SINCE'" ]

    symbolicNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "AND", "OR", "IMPLIES", "NOT", "EVENT", 
                      "ALWAYS", "UNTIL", "ONCE", "HIST", "SINCE", "BIGOP", 
                      "BOOLEAN", "VARIABLE", "RATIONAL", "WS" ]

    RULE_stlProperty = 0
    RULE_bound = 1
    RULE_expr = 2
    RULE_booleanExpr = 3

    ruleNames =  [ "stlProperty", "bound", "expr", "booleanExpr" ]

    EOF = Token.EOF
    T__0=1
    T__1=2
    T__2=3
    T__3=4
    T__4=5
    T__5=6
    T__6=7
    T__7=8
    T__8=9
    T__9=10
    T__10=11
    T__11=12
    T__12=13
    T__13=14
    T__14=15
    T__15=16
    AND=17
    OR=18
    IMPLIES=19
    NOT=20
    EVENT=21
    ALWAYS=22
    UNTIL=23
    ONCE=24
    HIST=25
    SINCE=26
    BIGOP=27
    BOOLEAN=28
    VARIABLE=29
    RATIONAL=30
    WS=31

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class StlPropertyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser


        def getRuleIndex(self):
            return pstlParser.RULE_stlProperty

     
        def copyFrom(self, ctx:ParserRuleContext):
            super().copyFrom(ctx)


    class BooleanPredContext(StlPropertyContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a pstlParser.StlPropertyContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def booleanExpr(self):
            return self.getTypedRuleContext(pstlParser.BooleanExprContext,0)


        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBooleanPred" ):
                listener.enterBooleanPred(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBooleanPred" ):
                listener.exitBooleanPred(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBooleanPred" ):
                return visitor.visitBooleanPred(self)
            else:
                return visitor.visitChildren(self)


    class FormulaContext(StlPropertyContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a pstlParser.StlPropertyContext
            super().__init__(parser)
            self.left = None # StlPropertyContext
            self.op = None # Token
            self.child = None # StlPropertyContext
            self.low = None # BoundContext
            self.high = None # BoundContext
            self.right = None # StlPropertyContext
            self.copyFrom(ctx)

        def NOT(self):
            return self.getToken(pstlParser.NOT, 0)
        def stlProperty(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(pstlParser.StlPropertyContext)
            else:
                return self.getTypedRuleContext(pstlParser.StlPropertyContext,i)

        def BIGOP(self):
            return self.getToken(pstlParser.BIGOP, 0)
        def EVENT(self):
            return self.getToken(pstlParser.EVENT, 0)
        def bound(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(pstlParser.BoundContext)
            else:
                return self.getTypedRuleContext(pstlParser.BoundContext,i)

        def ALWAYS(self):
            return self.getToken(pstlParser.ALWAYS, 0)
        def ONCE(self):
            return self.getToken(pstlParser.ONCE, 0)
        def HIST(self):
            return self.getToken(pstlParser.HIST, 0)
        def IMPLIES(self):
            return self.getToken(pstlParser.IMPLIES, 0)
        def AND(self):
            return self.getToken(pstlParser.AND, 0)
        def OR(self):
            return self.getToken(pstlParser.OR, 0)
        def UNTIL(self):
            return self.getToken(pstlParser.UNTIL, 0)
        def SINCE(self):
            return self.getToken(pstlParser.SINCE, 0)

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFormula" ):
                listener.enterFormula(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFormula" ):
                listener.exitFormula(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFormula" ):
                return visitor.visitFormula(self)
            else:
                return visitor.visitChildren(self)


    class ParpropContext(StlPropertyContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a pstlParser.StlPropertyContext
            super().__init__(parser)
            self.child = None # StlPropertyContext
            self.copyFrom(ctx)

        def stlProperty(self):
            return self.getTypedRuleContext(pstlParser.StlPropertyContext,0)


        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterParprop" ):
                listener.enterParprop(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitParprop" ):
                listener.exitParprop(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitParprop" ):
                return visitor.visitParprop(self)
            else:
                return visitor.visitChildren(self)



    def stlProperty(self, _p:int=0):
        _parentctx = self._ctx
        _parentState = self.state
        localctx = pstlParser.StlPropertyContext(self, self._ctx, _parentState)
        _prevctx = localctx
        _startState = 0
        self.enterRecursionRule(localctx, 0, self.RULE_stlProperty, _p)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 50
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,0,self._ctx)
            if la_ == 1:
                localctx = pstlParser.ParpropContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx

                self.state = 9
                self.match(pstlParser.T__0)
                self.state = 10
                localctx.child = self.stlProperty(0)
                self.state = 11
                self.match(pstlParser.T__1)
                pass

            elif la_ == 2:
                localctx = pstlParser.BooleanPredContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 13
                self.booleanExpr()
                pass

            elif la_ == 3:
                localctx = pstlParser.FormulaContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 14
                localctx.op = self.match(pstlParser.NOT)
                self.state = 15
                localctx.child = self.stlProperty(11)
                pass

            elif la_ == 4:
                localctx = pstlParser.FormulaContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 16
                localctx.op = self.match(pstlParser.BIGOP)
                self.state = 17
                localctx.child = self.stlProperty(10)
                pass

            elif la_ == 5:
                localctx = pstlParser.FormulaContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 18
                localctx.op = self.match(pstlParser.EVENT)
                self.state = 19
                self.match(pstlParser.T__2)
                self.state = 20
                localctx.low = self.bound()
                self.state = 21
                self.match(pstlParser.T__3)
                self.state = 22
                localctx.high = self.bound()
                self.state = 23
                self.match(pstlParser.T__4)
                self.state = 24
                localctx.child = self.stlProperty(9)
                pass

            elif la_ == 6:
                localctx = pstlParser.FormulaContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 26
                localctx.op = self.match(pstlParser.ALWAYS)
                self.state = 27
                self.match(pstlParser.T__2)
                self.state = 28
                localctx.low = self.bound()
                self.state = 29
                self.match(pstlParser.T__3)
                self.state = 30
                localctx.high = self.bound()
                self.state = 31
                self.match(pstlParser.T__4)
                self.state = 32
                localctx.child = self.stlProperty(8)
                pass

            elif la_ == 7:
                localctx = pstlParser.FormulaContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 34
                localctx.op = self.match(pstlParser.ONCE)
                self.state = 35
                self.match(pstlParser.T__2)
                self.state = 36
                localctx.low = self.bound()
                self.state = 37
                self.match(pstlParser.T__3)
                self.state = 38
                localctx.high = self.bound()
                self.state = 39
                self.match(pstlParser.T__4)
                self.state = 40
                localctx.child = self.stlProperty(7)
                pass

            elif la_ == 8:
                localctx = pstlParser.FormulaContext(self, localctx)
                self._ctx = localctx
                _prevctx = localctx
                self.state = 42
                localctx.op = self.match(pstlParser.HIST)
                self.state = 43
                self.match(pstlParser.T__2)
                self.state = 44
                localctx.low = self.bound()
                self.state = 45
                self.match(pstlParser.T__3)
                self.state = 46
                localctx.high = self.bound()
                self.state = 47
                self.match(pstlParser.T__4)
                self.state = 48
                localctx.child = self.stlProperty(6)
                pass


            self._ctx.stop = self._input.LT(-1)
            self.state = 81
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,2,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    self.state = 79
                    self._errHandler.sync(self)
                    la_ = self._interp.adaptivePredict(self._input,1,self._ctx)
                    if la_ == 1:
                        localctx = pstlParser.FormulaContext(self, pstlParser.StlPropertyContext(self, _parentctx, _parentState))
                        localctx.left = _prevctx
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_stlProperty)
                        self.state = 52
                        if not self.precpred(self._ctx, 5):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 5)")
                        self.state = 53
                        localctx.op = self.match(pstlParser.IMPLIES)
                        self.state = 54
                        localctx.right = self.stlProperty(6)
                        pass

                    elif la_ == 2:
                        localctx = pstlParser.FormulaContext(self, pstlParser.StlPropertyContext(self, _parentctx, _parentState))
                        localctx.left = _prevctx
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_stlProperty)
                        self.state = 55
                        if not self.precpred(self._ctx, 4):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 4)")
                        self.state = 56
                        localctx.op = self.match(pstlParser.AND)
                        self.state = 57
                        localctx.right = self.stlProperty(5)
                        pass

                    elif la_ == 3:
                        localctx = pstlParser.FormulaContext(self, pstlParser.StlPropertyContext(self, _parentctx, _parentState))
                        localctx.left = _prevctx
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_stlProperty)
                        self.state = 58
                        if not self.precpred(self._ctx, 3):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 3)")
                        self.state = 59
                        localctx.op = self.match(pstlParser.OR)
                        self.state = 60
                        localctx.right = self.stlProperty(4)
                        pass

                    elif la_ == 4:
                        localctx = pstlParser.FormulaContext(self, pstlParser.StlPropertyContext(self, _parentctx, _parentState))
                        localctx.left = _prevctx
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_stlProperty)
                        self.state = 61
                        if not self.precpred(self._ctx, 2):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 2)")
                        self.state = 62
                        localctx.op = self.match(pstlParser.UNTIL)
                        self.state = 63
                        self.match(pstlParser.T__2)
                        self.state = 64
                        localctx.low = self.bound()
                        self.state = 65
                        self.match(pstlParser.T__3)
                        self.state = 66
                        localctx.high = self.bound()
                        self.state = 67
                        self.match(pstlParser.T__4)
                        self.state = 68
                        localctx.right = self.stlProperty(3)
                        pass

                    elif la_ == 5:
                        localctx = pstlParser.FormulaContext(self, pstlParser.StlPropertyContext(self, _parentctx, _parentState))
                        localctx.left = _prevctx
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_stlProperty)
                        self.state = 70
                        if not self.precpred(self._ctx, 1):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 1)")
                        self.state = 71
                        localctx.op = self.match(pstlParser.SINCE)
                        self.state = 72
                        self.match(pstlParser.T__2)
                        self.state = 73
                        localctx.low = self.bound()
                        self.state = 74
                        self.match(pstlParser.T__3)
                        self.state = 75
                        localctx.high = self.bound()
                        self.state = 76
                        self.match(pstlParser.T__4)
                        self.state = 77
                        localctx.right = self.stlProperty(2)
                        pass

             
                self.state = 83
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,2,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.unrollRecursionContexts(_parentctx)
        return localctx


    class BoundContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def RATIONAL(self):
            return self.getToken(pstlParser.RATIONAL, 0)

        def VARIABLE(self):
            return self.getToken(pstlParser.VARIABLE, 0)

        def getRuleIndex(self):
            return pstlParser.RULE_bound

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBound" ):
                listener.enterBound(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBound" ):
                listener.exitBound(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBound" ):
                return visitor.visitBound(self)
            else:
                return visitor.visitChildren(self)




    def bound(self):

        localctx = pstlParser.BoundContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_bound)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 84
            _la = self._input.LA(1)
            if not(_la==29 or _la==30):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(pstlParser.ExprContext)
            else:
                return self.getTypedRuleContext(pstlParser.ExprContext,i)


        def VARIABLE(self):
            return self.getToken(pstlParser.VARIABLE, 0)

        def RATIONAL(self):
            return self.getToken(pstlParser.RATIONAL, 0)

        def getRuleIndex(self):
            return pstlParser.RULE_expr

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterExpr" ):
                listener.enterExpr(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitExpr" ):
                listener.exitExpr(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExpr" ):
                return visitor.visitExpr(self)
            else:
                return visitor.visitChildren(self)



    def expr(self, _p:int=0):
        _parentctx = self._ctx
        _parentState = self.state
        localctx = pstlParser.ExprContext(self, self._ctx, _parentState)
        _prevctx = localctx
        _startState = 4
        self.enterRecursionRule(localctx, 4, self.RULE_expr, _p)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 105
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,4,self._ctx)
            if la_ == 1:
                self.state = 87
                _la = self._input.LA(1)
                if not(_la==1 or _la==6):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 88
                self.expr(0)
                self.state = 89
                self.match(pstlParser.T__1)
                pass

            elif la_ == 2:
                self.state = 91
                self.match(pstlParser.VARIABLE)
                self.state = 92
                self.match(pstlParser.T__0)
                self.state = 93
                self.expr(0)
                self.state = 98
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while _la==4:
                    self.state = 94
                    self.match(pstlParser.T__3)
                    self.state = 95
                    self.expr(0)
                    self.state = 100
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)

                self.state = 101
                self.match(pstlParser.T__1)
                pass

            elif la_ == 3:
                self.state = 103
                self.match(pstlParser.RATIONAL)
                pass

            elif la_ == 4:
                self.state = 104
                self.match(pstlParser.VARIABLE)
                pass


            self._ctx.stop = self._input.LT(-1)
            self.state = 118
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,6,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    self.state = 116
                    self._errHandler.sync(self)
                    la_ = self._interp.adaptivePredict(self._input,5,self._ctx)
                    if la_ == 1:
                        localctx = pstlParser.ExprContext(self, _parentctx, _parentState)
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 107
                        if not self.precpred(self._ctx, 6):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 6)")
                        self.state = 108
                        self.match(pstlParser.T__6)
                        self.state = 109
                        self.expr(6)
                        pass

                    elif la_ == 2:
                        localctx = pstlParser.ExprContext(self, _parentctx, _parentState)
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 110
                        if not self.precpred(self._ctx, 4):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 4)")
                        self.state = 111
                        _la = self._input.LA(1)
                        if not(_la==8 or _la==9):
                            self._errHandler.recoverInline(self)
                        else:
                            self._errHandler.reportMatch(self)
                            self.consume()
                        self.state = 112
                        self.expr(5)
                        pass

                    elif la_ == 3:
                        localctx = pstlParser.ExprContext(self, _parentctx, _parentState)
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 113
                        if not self.precpred(self._ctx, 3):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 3)")
                        self.state = 114
                        _la = self._input.LA(1)
                        if not(_la==10 or _la==11):
                            self._errHandler.recoverInline(self)
                        else:
                            self._errHandler.reportMatch(self)
                            self.consume()
                        self.state = 115
                        self.expr(4)
                        pass

             
                self.state = 120
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,6,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.unrollRecursionContexts(_parentctx)
        return localctx


    class BooleanExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.left = None # ExprContext
            self.op = None # Token
            self.right = None # ExprContext
            self.atom = None # Token

        def expr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(pstlParser.ExprContext)
            else:
                return self.getTypedRuleContext(pstlParser.ExprContext,i)


        def BOOLEAN(self):
            return self.getToken(pstlParser.BOOLEAN, 0)

        def VARIABLE(self):
            return self.getToken(pstlParser.VARIABLE, 0)

        def getRuleIndex(self):
            return pstlParser.RULE_booleanExpr

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBooleanExpr" ):
                listener.enterBooleanExpr(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBooleanExpr" ):
                listener.exitBooleanExpr(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBooleanExpr" ):
                return visitor.visitBooleanExpr(self)
            else:
                return visitor.visitChildren(self)




    def booleanExpr(self):

        localctx = pstlParser.BooleanExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_booleanExpr)
        self._la = 0 # Token type
        try:
            self.state = 140
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,9,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 121
                localctx.left = self.expr(0)
                self.state = 122
                localctx.op = self._input.LT(1)
                _la = self._input.LA(1)
                if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 126976) != 0)):
                    localctx.op = self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 123
                localctx.right = self.expr(0)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 125
                localctx.op = self.match(pstlParser.BOOLEAN)
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 126
                localctx.atom = self.match(pstlParser.VARIABLE)
                self.state = 138
                self._errHandler.sync(self)
                la_ = self._interp.adaptivePredict(self._input,8,self._ctx)
                if la_ == 1:
                    self.state = 127
                    self.match(pstlParser.T__0)
                    self.state = 128
                    self.expr(0)
                    self.state = 133
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    while _la==4:
                        self.state = 129
                        self.match(pstlParser.T__3)
                        self.state = 130
                        self.expr(0)
                        self.state = 135
                        self._errHandler.sync(self)
                        _la = self._input.LA(1)

                    self.state = 136
                    self.match(pstlParser.T__1)


                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx



    def sempred(self, localctx:RuleContext, ruleIndex:int, predIndex:int):
        if self._predicates == None:
            self._predicates = dict()
        self._predicates[0] = self.stlProperty_sempred
        self._predicates[2] = self.expr_sempred
        pred = self._predicates.get(ruleIndex, None)
        if pred is None:
            raise Exception("No predicate with index:" + str(ruleIndex))
        else:
            return pred(localctx, predIndex)

    def stlProperty_sempred(self, localctx:StlPropertyContext, predIndex:int):
            if predIndex == 0:
                return self.precpred(self._ctx, 5)
         

            if predIndex == 1:
                return self.precpred(self._ctx, 4)
         

            if predIndex == 2:
                return self.precpred(self._ctx, 3)
         

            if predIndex == 3:
                return self.precpred(self._ctx, 2)
         

            if predIndex == 4:
                return self.precpred(self._ctx, 1)
         

    def expr_sempred(self, localctx:ExprContext, predIndex:int):
            if predIndex == 5:
                return self.precpred(self._ctx, 6)
         

            if predIndex == 6:
                return self.precpred(self._ctx, 4)
         

            if predIndex == 7:
                return self.precpred(self._ctx, 3)
         




