package com.trading.hf.model;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

public class OptionChainData {

    @JsonProperty("strike")
    private int strike;

    @JsonProperty("call_oi")
    private int callOi;

    @JsonProperty("put_oi")
    private int putOi;

    @JsonProperty("call_oi_chg")
    private int callOiChg;

    @JsonProperty("put_oi_chg")
    private int putOiChg;

    public int getStrike() {
        return strike;
    }

    public void setStrike(int strike) {
        this.strike = strike;
    }

    public int getCallOi() {
        return callOi;
    }

    public void setCallOi(int callOi) {
        this.callOi = callOi;
    }

    public int getPutOi() {
        return putOi;
    }

    public void setPutOi(int putOi) {
        this.putOi = putOi;
    }

    public int getCallOiChg() {
        return callOiChg;
    }

    public void setCallOiChg(int callOiChg) {
        this.callOiChg = callOiChg;
    }

    public int getPutOiChg() {
        return putOiChg;
    }

    public void setPutOiChg(int putOiChg) {
        this.putOiChg = putOiChg;
    }
}
