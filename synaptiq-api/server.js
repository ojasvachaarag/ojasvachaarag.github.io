const express = require("express");
const cors = require("cors");
const { v4: uuidv4 } = require("uuid");

const app = express();

app.use(cors());
app.use(express.json());

const jobs = {};

/*
    ROOT
*/
app.get("/", (req, res) => {

    res.send("API Running");
});

/*
    START JOB
*/
app.post("/start-job", (req, res) => {

    const jobId = uuidv4();

    jobs[jobId] = {

        status: "running",

        result: null,

        prompt: req.body.prompt
    };

    console.log(
        "JOB CREATED:",
        jobs[jobId]
    );

    /*
        FAKE AI DELAY
    */
    setTimeout(()=>{

        jobs[jobId].status =
            "completed";

        jobs[jobId].result =
            `AI response to: ${jobs[jobId].prompt}`;

    }, 10000);

    res.json({

        success: true,

        jobId
    });
});

/*
    CHECK JOB STATUS
*/
app.get("/job/:id", (req, res) => {

    const job = jobs[req.params.id];

    if(!job){

        return res.status(404).json({
            error: "Job not found"
        });
    }

    res.json(job);
});

const PORT =
    process.env.PORT || 3000;

app.listen(PORT, ()=>{

    console.log(
        `Server running on ${PORT}`
    );
});