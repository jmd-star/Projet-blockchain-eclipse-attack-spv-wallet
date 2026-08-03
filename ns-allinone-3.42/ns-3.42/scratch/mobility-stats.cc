#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/lte-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include <fstream>

using namespace ns3;

std::ofstream g_traceFile;

void
StateTransitionCallback(std::string context, uint64_t imsi, uint16_t cellId, uint16_t rnti,
                         LteUeRrc::State oldState, LteUeRrc::State newState)
{
    g_traceFile << Simulator::Now().GetSeconds() << ","
                << imsi << "," << oldState << "," << newState << std::endl;
}

int
main(int argc, char* argv[])
{
    double speed = 5.0;
    double simTime = 300.0;
    double txPower = 46.0;
    std::string scenario = "moderate";
    std::string outFile = "results/raw/mobility_stats_moderate.csv";

    CommandLine cmd;
    cmd.AddValue("speed", "UE speed in m/s", speed);
    cmd.AddValue("simTime", "Simulation duration in seconds", simTime);
    cmd.AddValue("txPower", "eNB transmit power in dBm (lower = weaker signal)", txPower);
    cmd.AddValue("scenario", "Scenario label", scenario);
    cmd.AddValue("outFile", "Output CSV path", outFile);
    cmd.Parse(argc, argv);

    g_traceFile.open(outFile);
    g_traceFile << "time,imsi,oldState,newState" << std::endl;

    Ptr<LteHelper> lteHelper = CreateObject<LteHelper>();
    Ptr<PointToPointEpcHelper> epcHelper = CreateObject<PointToPointEpcHelper>();
    lteHelper->SetEpcHelper(epcHelper);
    lteHelper->SetHandoverAlgorithmType("ns3::A3RsrpHandoverAlgorithm");
    lteHelper->SetHandoverAlgorithmAttribute("Hysteresis", DoubleValue(3.0));
    lteHelper->SetHandoverAlgorithmAttribute("TimeToTrigger", TimeValue(MilliSeconds(256)));

    Config::SetDefault("ns3::LteEnbPhy::TxPower", DoubleValue(txPower));

    NodeContainer enbNodes;
    enbNodes.Create(2);
    NodeContainer ueNodes;
    ueNodes.Create(1);

    MobilityHelper enbMobility;
    enbMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    Ptr<ListPositionAllocator> enbPositions = CreateObject<ListPositionAllocator>();
    enbPositions->Add(Vector(0.0, 0.0, 0.0));
    enbPositions->Add(Vector(500.0, 0.0, 0.0));
    enbMobility.SetPositionAllocator(enbPositions);
    enbMobility.Install(enbNodes);

    MobilityHelper ueMobility;
    if (scenario == "wired" || speed == 0.0)
    {
        ueMobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
        Ptr<ListPositionAllocator> uePosAlloc = CreateObject<ListPositionAllocator>();
        uePosAlloc->Add(Vector(0.0, 10.0, 0.0));
        ueMobility.SetPositionAllocator(uePosAlloc);
    }
    else
    {
        Ptr<UniformRandomVariable> xVar = CreateObject<UniformRandomVariable>();
        xVar->SetAttribute("Min", DoubleValue(0.0));
        xVar->SetAttribute("Max", DoubleValue(500.0));

        Ptr<UniformRandomVariable> yVar = CreateObject<UniformRandomVariable>();
        yVar->SetAttribute("Min", DoubleValue(0.0));
        yVar->SetAttribute("Max", DoubleValue(20.0));

        Ptr<UniformRandomVariable> zVar = CreateObject<UniformRandomVariable>();
        zVar->SetAttribute("Min", DoubleValue(0.0));
        zVar->SetAttribute("Max", DoubleValue(0.0));

        Ptr<RandomBoxPositionAllocator> boxPosAlloc = CreateObject<RandomBoxPositionAllocator>();
        boxPosAlloc->SetAttribute("X", PointerValue(xVar));
        boxPosAlloc->SetAttribute("Y", PointerValue(yVar));
        boxPosAlloc->SetAttribute("Z", PointerValue(zVar));

        ueMobility.SetPositionAllocator(boxPosAlloc);
        ueMobility.SetMobilityModel(
            "ns3::RandomWaypointMobilityModel",
            "Speed", StringValue("ns3::ConstantRandomVariable[Constant=" + std::to_string(speed) + "]"),
            "Pause", StringValue("ns3::ConstantRandomVariable[Constant=0.0]"),
            "PositionAllocator", PointerValue(boxPosAlloc));
    }
    ueMobility.Install(ueNodes);

    NetDeviceContainer enbDevs = lteHelper->InstallEnbDevice(enbNodes);
    NetDeviceContainer ueDevs = lteHelper->InstallUeDevice(ueNodes);

    InternetStackHelper internet;
    internet.Install(ueNodes);
    epcHelper->AssignUeIpv4Address(NetDeviceContainer(ueDevs));

    lteHelper->Attach(ueDevs.Get(0), enbDevs.Get(0));
    lteHelper->AddX2Interface(enbNodes);

    Config::Connect("/NodeList/*/DeviceList/*/LteUeRrc/StateTransition",
                     MakeCallback(&StateTransitionCallback));

    Simulator::Stop(Seconds(simTime));
    Simulator::Run();
    Simulator::Destroy();

    g_traceFile.close();
    return 0;
}
