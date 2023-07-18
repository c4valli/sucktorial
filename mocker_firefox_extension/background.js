const INTERESTING_URLS = [
    // Employee's companies with some permissions
    "https://api.factorialhr.com/companies",
    // Called to check if the user has a specific permission
    "https://api.factorialhr.com/permissions/permissions/authorize_policies",
    // Announcements and celebrations, permissions to add posts
    "https://api.factorialhr.com/posts/groups",
];

const NOT_INTERESTING_URLS = [
    // Empty or meaningless responses
    "https://api.factorialhr.com/ats/companies",
    "https://api.factorialhr.com/teams",
    "https://api.factorialhr.com/company_holidays",
    "https://api.factorialhr.com/memberships",
    "https://api.factorialhr.com/visits",
    "https://api.factorialhr.com/accesses/become",
    "https://api.factorialhr.com/api/rest/marketplace/user_installation",
    "https://api.factorialhr.com/job_catalog/salary_ranges",
    "https://api.factorialhr.com/job_catalog/roles",
    "https://api.factorialhr.com/job_catalog/levels",
    "https://api.factorialhr.com/genders",
    "https://api.factorialhr.com/legal_genders",
    // Company legal entity
    "https://api.factorialhr.com/legal_entities",
    // Company address and contacts
    "https://api.factorialhr.com/locations",
    // Active subscription plan
    "https://api.factorialhr.com/billing/subscriptions",
    // Company policies (e.g. time off policy)
    "https://api.factorialhr.com/policies",
];

console.log("Factorial mocker running ...");

function mock_companies(response) {

    console.log("Companies original response:");
    console.log(response);

    if (Array.isArray(response) && response.length > 0) {
        for (const company of response) {
            if (company.permissions?.attendance) {
                company.permissions.attendance.approve = true;
            }
            if (company.permissions?.payroll) {
                company.permissions.payroll.edit_supplements = true;
            }
        }
    }

    console.log("Companies mocked response:");
    console.log(response);
}

function mock_authorize_policies(response) {

    const MOCK_POLICIES = [
        "contracts.create_additional_compensation_type",
        "contracts.delete_contracts",
        "contracts.edit",
        "contracts.promote",
        "contracts.read",
        "contracts.see_end_date",
        "employee.create",
        "employee.invite",
        "employee.become",
        "employee_profile.company_identifier.edit",
        "employee_profile.company_identifier.see",
        "finance.cost_center_memberships.see",
        "goals.read",
        "leaves.download",
        "payroll.manage_payroll",
        "planning_versions.edit",
        "planning_versions.read",
        "shift_management.create_shifts",
        "teams.manage",
    ];

    if (Array.isArray(response) && response.length > 0) {
        for (const policy of response) {
            
            let mocked = '';

            if (MOCK_POLICIES.includes(policy.policy_key)) {
                if (!policy.authorize) {
                    policy.authorize = true;
                    mocked = ' (mocked)';
                }
            }

            console.log(`${policy.policy_key}, ${policy.authorize}, ${policy.target_id}${policy.target_resource} ${mocked}`);
        }
    }
}

function handle_mocking(url, response) {
    switch (url) {
        case "https://api.factorialhr.com/companies":
            mock_companies(response);
            break;
        case "https://api.factorialhr.com/permissions/permissions/authorize_policies":
            mock_authorize_policies(response);
            break;
        default:
            console.log(`No mocker for: ${url}`);
            console.log(response);
            break;
    }
}

function mocker(requestDetails) {

    if (!NOT_INTERESTING_URLS.includes(requestDetails.url)) {
        let filter = browser.webRequest.filterResponseData(requestDetails.requestId);
        let decoder = new TextDecoder("utf-8");
        let encoder = new TextEncoder();

        filter.ondata = (event) => {
            let str = decoder.decode(event.data, { stream: true });
            
            try {
                const response = JSON.parse(str);

                handle_mocking(requestDetails.url, response);

                filter.write(encoder.encode(JSON.stringify(response)));
            } catch (e) {
                filter.write(encoder.encode(str));
            }
            filter.disconnect();
        };
    }
  
    return {};
}

browser.webRequest.onBeforeRequest.addListener(
    mocker,
    {
        urls: ["*://api.factorialhr.com/*"],
    },
    ["blocking"]
);
