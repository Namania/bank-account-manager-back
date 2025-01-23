const element = document.getElementById("json");
const json = JSON.parse(element.innerText);

const colors = {
    "pink": [
        'rgba(255, 99, 132, 0.2)',
        'rgb(255, 99, 132)'
    ],
    "orange": [
        'rgba(255, 159, 64, 0.2)',
        'rgb(255, 159, 64)'
    ],
    "yellow": [
        'rgba(255, 205, 86, 0.2)',
        'rgb(255, 205, 86)'
    ],
    "light-blue": [
        'rgba(75, 192, 192, 0.2)',
        'rgb(75, 192, 192)'
    ],
    "blue": [
        'rgba(54, 162, 235, 0.2)',
        'rgb(54, 162, 235)'
    ],
    "purple": [
        'rgba(153, 102, 255, 0.2)',
        'rgb(153, 102, 255)'
    ]
}

const backgroundColor = [];
const borderColor = [];

json["color"].forEach(color => {
    backgroundColor.push(colors[color][0]);
    borderColor.push(colors[color][1]);
});

const labels = json["labels"];
const data = {
    labels: labels,
    datasets: [{
        label: 'Balance',
        data: [
            ...json["data"],
        ],
        backgroundColor: [
            ...backgroundColor,
        ],
        borderColor: [
            ...borderColor,
        ],
        borderWidth: 1
    }],
};

const options = {
    legend: {
        display: false,
    },
    scales: {
        yAxes: [{
            ticks: {
                beginAtZero: true
            }
        }]
    },
};

const config = {
    type: 'bar',
    data: data,
    options
};

window.onload = function() {
    var ctx = document.getElementById('pie-chart').getContext('2d');
    window.myPie = new Chart(ctx, config);
};
