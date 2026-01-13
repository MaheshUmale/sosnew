package com.trading.hf.model;

public class Sentiment {
    private double pcr;
    private double pcrVelocity;
    private int advances;
    private int declines;
    private double oiWallAbove;
    private double oiWallBelow;
    private String regime;

    // Getters and setters
    public double getPcr() {
        return pcr;
    }

    public void setPcr(double pcr) {
        this.pcr = pcr;
    }

    public double getPcrVelocity() {
        return pcrVelocity;
    }

    public void setPcrVelocity(double pcrVelocity) {
        this.pcrVelocity = pcrVelocity;
    }

    public int getAdvances() {
        return advances;
    }

    public void setAdvances(int advances) {
        this.advances = advances;
    }

    public int getDeclines() {
        return declines;
    }

    public void setDeclines(int declines) {
        this.declines = declines;
    }

    public double getOiWallAbove() {
        return oiWallAbove;
    }

    public void setOiWallAbove(double oiWallAbove) {
        this.oiWallAbove = oiWallAbove;
    }

    public double getOiWallBelow() {
        return oiWallBelow;
    }

    public void setOiWallBelow(double oiWallBelow) {
        this.oiWallBelow = oiWallBelow;
    }

    public String getRegime() {
        return regime;
    }

    public void setRegime(String regime) {
        this.regime = regime;
    }
}
